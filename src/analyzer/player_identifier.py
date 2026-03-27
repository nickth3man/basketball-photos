"""
Player identification orchestrator that combines detection, OCR, and roster matching.

Coordinates the full pipeline:
1. Detect persons in image using YOLO
2. OCR jersey numbers from cropped detections using EasyOCR
3. Match jersey numbers to NBA players using roster data

Provides lazy loading for all components and graceful degradation when
optional dependencies are not available.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.analyzer.jersey_ocr import JerseyOCR
from src.analyzer.player_detector import PlayerDetector
from src.analyzer.roster_matcher import RosterMatcher
from src.logging_config import get_logger
from src.types.config import Config
from src.types.errors import ImageProcessingError
from src.types.player_identification import PlayerDetectionResult, PlayerIdentity

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class PlayerIdentifier:
    """Orchestrates player identification pipeline.

    Combines person detection, jersey OCR, and roster matching to identify
    NBA players in basketball photos. Uses lazy loading for all components
    and provides graceful degradation when dependencies are unavailable.

    Attributes:
        config: Application configuration.
        enabled: Whether player identification is enabled.
        auto_approve_threshold: Confidence threshold for auto-approval.
        review_threshold: Minimum confidence for keeping results.

    Example:
        >>> from src.config.loader import load_config
        >>> config = load_config()
        >>> identifier = PlayerIdentifier(config)
        >>> results = identifier.identify("./images/game.jpg", team_hint="LAL")
        >>> for player in results:
        ...     print(f"{player.name} #{player.jersey_number} ({player.confidence:.0%})")
    """

    def __init__(self, config: Config) -> None:
        """Initialize the PlayerIdentifier with configuration.

        Args:
            config: Application configuration containing player_identification settings.
        """
        self.config = config
        self._enabled = config.player_identification.enabled
        self._auto_approve_threshold = (
            config.player_identification.auto_approve_threshold
        )
        self._review_threshold = config.player_identification.review_threshold
        self._enable_detection = config.player_identification.enable_detection
        self._enable_ocr = config.player_identification.enable_ocr
        self._enable_roster = config.player_identification.enable_roster

        # Lazy-loaded components
        self._detector: PlayerDetector | None = None
        self._ocr: JerseyOCR | None = None
        self._roster_matcher: RosterMatcher | None = None

        log.debug(
            "player_identifier_initialized",
            enabled=self._enabled,
            auto_approve_threshold=self._auto_approve_threshold,
            review_threshold=self._review_threshold,
            enable_detection=self._enable_detection,
            enable_ocr=self._enable_ocr,
            enable_roster=self._enable_roster,
        )

    @property
    def enabled(self) -> bool:
        """Check if player identification is enabled."""
        return self._enabled

    @property
    def auto_approve_threshold(self) -> float:
        """Get the auto-approval confidence threshold."""
        return self._auto_approve_threshold

    @property
    def review_threshold(self) -> float:
        """Get the minimum confidence threshold for keeping results."""
        return self._review_threshold

    @property
    def detector(self) -> PlayerDetector:
        """Lazily initialize and return the player detector.

        Returns:
            PlayerDetector instance.
        """
        if self._detector is None:
            log.info("initializing_player_detector")
            self._detector = PlayerDetector(
                confidence_threshold=self.config.player_identification.confidence_threshold
            )
        return self._detector

    @property
    def ocr(self) -> JerseyOCR:
        """Lazily initialize and return the jersey OCR.

        Returns:
            JerseyOCR instance.
        """
        if self._ocr is None:
            log.info("initializing_jersey_ocr")
            self._ocr = JerseyOCR(
                confidence_threshold=self.config.player_identification.confidence_threshold
            )
        return self._ocr

    @property
    def roster_matcher(self) -> RosterMatcher:
        """Lazily initialize and return the roster matcher.

        Returns:
            RosterMatcher instance.
        """
        if self._roster_matcher is None:
            log.info("initializing_roster_matcher")
            self._roster_matcher = RosterMatcher(
                cache_ttl=self.config.player_identification.roster_cache_ttl
            )
        return self._roster_matcher

    def is_available(self) -> bool:
        """Check if player identification is available.

        Returns:
            True if identification is enabled and at least one component is available.
        """
        if not self._enabled:
            return False

        # Check if at least detection is available
        return self.detector.is_available()

    def identify(
        self,
        image_path: str | Path,
        team_hint: str | None = None,
    ) -> list[PlayerIdentity]:
        """Identify players in a single image.

        Pipeline:
        1. Detect persons in the image
        2. OCR jersey numbers from each detection
        3. Match jersey numbers to roster
        4. Create PlayerIdentity results

        Args:
            image_path: Path to the image file.
            team_hint: Optional team abbreviation (e.g., "LAL") to narrow roster search.

        Returns:
            List of PlayerIdentity objects for each identified player.
            Empty list if identification is disabled or no players detected.

        Raises:
            ImageProcessingError: If image cannot be processed.

        Example:
            >>> results = identifier.identify("./images/dunk.jpg", team_hint="LAL")
            >>> for player in results:
            ...     print(f"{player.name} (#{player.jersey_number})")
        """
        image_path = Path(image_path)

        # Check if identification is enabled
        if not self._enabled:
            log.debug(
                "identification_skipped_disabled",
                image_path=str(image_path),
            )
            return []

        start_time = time.perf_counter()

        log.info(
            "identification_started",
            image_path=str(image_path),
            team_hint=team_hint,
        )

        try:
            # Step 1: Detect persons
            detections = self._detect_players(image_path)

            if not detections:
                log.info(
                    "identification_complete_no_detections",
                    image_path=str(image_path),
                    elapsed_ms=(time.perf_counter() - start_time) * 1000,
                )
                return []

            # Step 2 & 3: OCR and match for each detection
            identities: list[PlayerIdentity] = []

            for detection in detections:
                identity = self._process_detection(
                    detection=detection,
                    team_hint=team_hint,
                    image_path=str(image_path),
                )
                if identity is not None:
                    identities.append(identity)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            log.info(
                "identification_complete",
                image_path=str(image_path),
                total_detections=len(detections),
                identified_players=len(identities),
                elapsed_ms=elapsed_ms,
            )

            return identities

        except Exception as error:
            if isinstance(error, ImageProcessingError):
                raise
            raise ImageProcessingError(
                f"Player identification failed: {error}",
                str(image_path),
            ) from error

    def _detect_players(self, image_path: Path) -> list[dict[str, Any]]:
        """Detect players in an image.

        Args:
            image_path: Path to the image file.

        Returns:
            List of detection dictionaries with bbox, confidence, and cropped_image.
        """
        if not self._enable_detection:
            log.debug("detection_skipped_disabled", image_path=str(image_path))
            return []

        if not self.detector.is_available():
            log.warning(
                "detection_skipped_unavailable",
                image_path=str(image_path),
                hint="Install ultralytics: pip install ultralytics",
            )
            return []

        return self.detector.detect(image_path)

    def _process_detection(
        self,
        detection: dict[str, Any],
        team_hint: str | None,
        image_path: str,
    ) -> PlayerIdentity | None:
        """Process a single detection through OCR and roster matching.

        Args:
            detection: Detection dict with bbox, confidence, and cropped_image.
            team_hint: Optional team abbreviation for roster lookup.
            image_path: Image path for logging context.

        Returns:
            PlayerIdentity if player was identified, None otherwise.
        """
        detection_conf = detection.get("confidence", 0.0)
        bbox = detection.get("bbox", [])
        cropped_image = detection.get("cropped_image")

        if cropped_image is None:
            log.debug(
                "detection_skipped_no_crop",
                image_path=image_path,
                bbox=bbox,
            )
            return None

        # Step 2: OCR jersey number
        ocr_results = self._ocr_jersey(cropped_image, image_path)

        if not ocr_results:
            log.debug(
                "ocr_no_results",
                image_path=image_path,
                bbox=bbox,
                detection_conf=detection_conf,
            )
            return None

        # Step 3: Match to roster
        best_identity: PlayerIdentity | None = None
        best_confidence = 0.0

        for jersey_number, ocr_conf in ocr_results:
            identity = self._match_to_roster(
                jersey_number=jersey_number,
                ocr_confidence=ocr_conf,
                detection_confidence=detection_conf,
                bbox=bbox,
                team_hint=team_hint,
                image_path=image_path,
            )

            if identity is not None and identity.confidence > best_confidence:
                best_identity = identity
                best_confidence = identity.confidence

        return best_identity

    def _ocr_jersey(
        self,
        cropped_image: Any,
        image_path: str,
    ) -> list[tuple[str, float]]:
        """OCR jersey number from cropped player image.

        Args:
            cropped_image: Numpy array of cropped player region.
            image_path: Image path for logging context.

        Returns:
            List of (jersey_number, confidence) tuples sorted by confidence.
        """
        if not self._enable_ocr:
            log.debug("ocr_skipped_disabled", image_path=image_path)
            return []

        if not self.ocr.is_available():
            log.debug(
                "ocr_skipped_unavailable",
                image_path=image_path,
                hint="Install easyocr: pip install easyocr",
            )
            return []

        try:
            return self.ocr.recognize(cropped_image)
        except Exception as error:
            log.warning(
                "ocr_failed",
                image_path=image_path,
                error=str(error),
            )
            return []

    def _match_to_roster(
        self,
        jersey_number: str,
        ocr_confidence: float,
        detection_confidence: float,
        bbox: list[int],
        team_hint: str | None,
        image_path: str,
    ) -> PlayerIdentity | None:
        """Match jersey number to player roster.

        Args:
            jersey_number: Recognized jersey number string.
            ocr_confidence: OCR confidence score.
            detection_confidence: Detection confidence score.
            bbox: Bounding box coordinates.
            team_hint: Optional team abbreviation.
            image_path: Image path for logging context.

        Returns:
            PlayerIdentity if matched, None otherwise.
        """
        if not self._enable_roster or not team_hint:
            # Create unidentified player identity
            overall_conf = self._calculate_confidence(
                detection_confidence, ocr_confidence, roster_matched=False
            )

            if overall_conf < self._review_threshold:
                return None

            return PlayerIdentity(
                player_id=0,
                name="",
                jersey_number=jersey_number,
                team=team_hint or "",
                confidence=overall_conf,
                detection_confidence=detection_confidence,
                ocr_confidence=ocr_confidence,
                bbox=bbox,
                review_status="needs_review",
                method="jersey_ocr",
            )

        if not self.roster_matcher.is_available:
            log.debug(
                "roster_skipped_unavailable",
                image_path=image_path,
                hint="Install nba_api: pip install nba_api",
            )
            return None

        try:
            player_info = self.roster_matcher.match_jersey_to_player(
                team=team_hint,
                jersey_number=jersey_number,
            )

            if player_info is None:
                log.debug(
                    "roster_no_match",
                    image_path=image_path,
                    jersey_number=jersey_number,
                    team=team_hint,
                )
                return None

            overall_conf = self._calculate_confidence(
                detection_confidence, ocr_confidence, roster_matched=True
            )

            if overall_conf < self._review_threshold:
                log.debug(
                    "identity_below_threshold",
                    image_path=image_path,
                    jersey_number=jersey_number,
                    confidence=overall_conf,
                    threshold=self._review_threshold,
                )
                return None

            review_status = (
                "auto_approved"
                if overall_conf >= self._auto_approve_threshold
                else "needs_review"
            )

            log.info(
                "player_identified",
                image_path=image_path,
                player_name=player_info.name,
                jersey_number=jersey_number,
                team=player_info.team,
                confidence=overall_conf,
                review_status=review_status,
            )

            return PlayerIdentity(
                player_id=player_info.player_id,
                name=player_info.name,
                jersey_number=jersey_number,
                team=player_info.team,
                confidence=overall_conf,
                detection_confidence=detection_confidence,
                ocr_confidence=ocr_confidence,
                bbox=bbox,
                review_status=review_status,
                method="jersey_ocr",
            )

        except Exception as error:
            log.warning(
                "roster_match_failed",
                image_path=image_path,
                jersey_number=jersey_number,
                team=team_hint,
                error=str(error),
            )
            return None

    def _calculate_confidence(
        self,
        detection_confidence: float,
        ocr_confidence: float,
        roster_matched: bool,
    ) -> float:
        """Calculate overall identification confidence.

        Weights:
        - Detection: 30%
        - OCR: 40%
        - Roster match bonus: +30%

        Args:
            detection_confidence: YOLO detection confidence.
            ocr_confidence: EasyOCR confidence.
            roster_matched: Whether jersey was matched to roster.

        Returns:
            Overall confidence score (0.0-1.0).
        """
        # Base confidence from detection and OCR
        base_confidence = (detection_confidence * 0.3) + (ocr_confidence * 0.4)

        # Roster match bonus
        roster_bonus = 0.3 if roster_matched else 0.0

        overall = base_confidence + roster_bonus

        # Clamp to [0, 1]
        return min(max(overall, 0.0), 1.0)

    def identify_batch(
        self,
        image_paths: list[str | Path],
        team_hint: str | None = None,
        parallel: bool = True,
        max_workers: int = 4,
    ) -> list[PlayerDetectionResult]:
        """Identify players in multiple images.

        Args:
            image_paths: List of image file paths.
            team_hint: Optional team abbreviation for all images.
            parallel: Whether to process images in parallel (default: True).
            max_workers: Maximum number of parallel workers (default: 4).

        Returns:
            List of PlayerDetectionResult objects, one per image.

        Example:
            >>> paths = ["./images/game1.jpg", "./images/game2.jpg"]
            >>> results = identifier.identify_batch(paths, team_hint="LAL")
            >>> for result in results:
            ...     print(f"{result.photo_path}: {result.total_detections} players")
        """
        if not self._enabled:
            log.debug("batch_identification_skipped_disabled")
            return []

        if not image_paths:
            return []

        log.info(
            "batch_identification_started",
            image_count=len(image_paths),
            team_hint=team_hint,
            parallel=parallel,
            max_workers=max_workers,
        )

        start_time = time.perf_counter()

        if parallel and len(image_paths) > 1:
            results = self._process_batch_parallel(
                image_paths=image_paths,
                team_hint=team_hint,
                max_workers=max_workers,
            )
        else:
            results = self._process_batch_sequential(
                image_paths=image_paths,
                team_hint=team_hint,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        log.info(
            "batch_identification_complete",
            image_count=len(image_paths),
            total_detections=sum(r.total_detections for r in results),
            elapsed_ms=elapsed_ms,
        )

        return results

    def _process_batch_parallel(
        self,
        image_paths: list[str | Path],
        team_hint: str | None,
        max_workers: int,
    ) -> list[PlayerDetectionResult]:
        """Process batch of images in parallel using ThreadPoolExecutor.

        Args:
            image_paths: List of image paths.
            team_hint: Optional team abbreviation.
            max_workers: Maximum parallel workers.

        Returns:
            List of PlayerDetectionResult objects.
        """
        results: list[PlayerDetectionResult] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(
                    self._process_single_for_batch,
                    path,
                    team_hint,
                ): path
                for path in image_paths
            }

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as error:
                    log.error(
                        "batch_processing_failed",
                        image_path=str(path),
                        error=str(error),
                    )
                    # Create error result
                    results.append(
                        PlayerDetectionResult(
                            photo_path=str(path),
                            photo_id=0,
                            errors=[str(error)],
                        )
                    )

        # Sort results to match input order
        path_to_result = {r.photo_path: r for r in results}
        return [
            path_to_result.get(
                str(p), PlayerDetectionResult(photo_path=str(p), photo_id=0)
            )
            for p in image_paths
        ]

    def _process_batch_sequential(
        self,
        image_paths: list[str | Path],
        team_hint: str | None,
    ) -> list[PlayerDetectionResult]:
        """Process batch of images sequentially.

        Args:
            image_paths: List of image paths.
            team_hint: Optional team abbreviation.

        Returns:
            List of PlayerDetectionResult objects.
        """
        results: list[PlayerDetectionResult] = []

        for path in image_paths:
            try:
                result = self._process_single_for_batch(path, team_hint)
                results.append(result)
            except Exception as error:
                log.error(
                    "batch_processing_failed",
                    image_path=str(path),
                    error=str(error),
                )
                results.append(
                    PlayerDetectionResult(
                        photo_path=str(path),
                        photo_id=0,
                        errors=[str(error)],
                    )
                )

        return results

    def _process_single_for_batch(
        self,
        image_path: str | Path,
        team_hint: str | None,
    ) -> PlayerDetectionResult:
        """Process a single image and return a PlayerDetectionResult.

        Args:
            image_path: Path to the image.
            team_hint: Optional team abbreviation.

        Returns:
            PlayerDetectionResult with all detected players.
        """
        start_time = time.perf_counter()

        try:
            identities = self.identify(image_path, team_hint=team_hint)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return PlayerDetectionResult(
                photo_path=str(image_path),
                photo_id=0,  # Will be set by caller if persisted
                detections=identities,
                processing_time_ms=elapsed_ms,
            )
        except Exception as error:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return PlayerDetectionResult(
                photo_path=str(image_path),
                photo_id=0,
                processing_time_ms=elapsed_ms,
                errors=[str(error)],
            )

    def __repr__(self) -> str:
        return (
            f"PlayerIdentifier(enabled={self._enabled}, "
            f"auto_approve_threshold={self._auto_approve_threshold}, "
            f"review_threshold={self._review_threshold})"
        )
