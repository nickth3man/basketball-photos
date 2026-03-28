"""
YOLO-based person detection for basketball photo analysis.

Provides PlayerDetector class with lazy model loading and graceful degradation
when ultralytics is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from src.logging_config import get_logger
from src.types.errors import ImageReadError, ImageProcessingError

if TYPE_CHECKING:
    from ultralytics import YOLO as YOLOModel  # type: ignore[import-not-found]

logger = get_logger(__name__)

# Optional dependency handling
YOLO: type["YOLOModel"] | None = None

try:
    from ultralytics import YOLO  # type: ignore[import-not-found]

    HAS_ULTRALYTICS = True
except ImportError:
    HAS_ULTRALYTICS = False
    logger.warning(
        "ultralytics not available, player detection will return empty results. "
        "Install with: pip install ultralytics"
    )

# YOLO class ID for person detection
PERSON_CLASS_ID = 0


class PlayerDetector:
    """
    Detect players (persons) in basketball photos using YOLOv8.

    Uses lazy loading for the YOLO model - model is loaded on first detection,
    not at import time. Provides graceful degradation when ultralytics is not
    installed.

    Attributes:
        confidence_threshold: Minimum confidence score for detections (0.0-1.0).
        model_name: YOLO model variant to use.

    Example:
        detector = PlayerDetector(confidence_threshold=0.5)
        results = detector.detect("./images/photo.jpg")
        for detection in results:
            print(f"Player found at {detection['bbox']} with {detection['confidence']:.2f} confidence")
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        model_name: str = "yolov8n.pt",
    ):
        """
        Initialize the PlayerDetector.

        Args:
            confidence_threshold: Minimum confidence for detections (default: 0.5).
                                  Detections below this threshold are filtered out.
            model_name: YOLO model variant (default: "yolov8n.pt" for fastest CPU inference).
                        Options include: yolov8n.pt (nano), yolov8s.pt (small),
                        yolov8m.pt (medium), yolov8l.pt (large).
        """
        self.confidence_threshold = confidence_threshold
        self.model_name = model_name
        self._model: "YOLOModel | None" = None

    @property
    def model(self) -> "YOLOModel | None":
        """
        Lazily load and return the YOLO model.

        The model is loaded on first access, not at initialization.
        Returns None if ultralytics is not installed.

        Returns:
            YOLO model instance or None if unavailable.
        """
        if not HAS_ULTRALYTICS:
            logger.debug("ultralytics_not_available", model_name=self.model_name)
            return None

        if self._model is None:
            logger.info(
                "loading_yolo_model",
                model_name=self.model_name,
                note="Model downloads automatically on first use",
            )
            self._model = YOLO(self.model_name)  # type: ignore[assignment]
            logger.info("yolo_model_loaded", model_name=self.model_name)

        return self._model

    def is_available(self) -> bool:
        """
        Check if player detection is available.

        Returns:
            True if ultralytics is installed and model can be loaded.
        """
        return HAS_ULTRALYTICS

    def detect(self, image_path: str | Path) -> list[dict[str, Any]]:
        """
        Detect players (persons) in an image.

        Args:
            image_path: Path to the image file.

        Returns:
            List of detection dictionaries, each containing:
                - "bbox": [x1, y1, x2, y2] bounding box coordinates
                - "confidence": Detection confidence score (0.0-1.0)
                - "cropped_image": numpy array of the cropped region (RGB)

            Returns empty list if:
                - ultralytics is not installed
                - No persons detected above confidence threshold
                - Image cannot be loaded

        Raises:
            ImageReadError: If the image file cannot be read.
            ImageProcessingError: If image processing fails.

        Example:
            results = detector.detect("./images/dunk.jpg")
            for det in results:
                x1, y1, x2, y2 = det["bbox"]
                print(f"Player detected at ({x1}, {y1}) to ({x2}, {y2})")
        """
        image_path = Path(image_path)

        # Check if ultralytics is available
        if not self.is_available():
            logger.debug(
                "detection_skipped_ultralytics_unavailable",
                image_path=str(image_path),
            )
            return []

        # Validate image exists
        if not image_path.exists():
            raise ImageReadError(f"Image file not found: {image_path}", str(image_path))

        # Get model (lazy load)
        model = self.model
        if model is None:
            logger.warning(
                "detection_failed_model_unavailable",
                image_path=str(image_path),
            )
            return []

        try:
            # Load image for cropping  # sourcery: skip
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                img_array = np.array(img_rgb)
                img_width, img_height = img.size

            logger.debug(
                "starting_detection",
                image_path=str(image_path),
                image_size=f"{img_width}x{img_height}",
                confidence_threshold=self.confidence_threshold,
            )

            # Run YOLO inference - filter for person class only
            results = model(
                str(image_path),
                classes=[PERSON_CLASS_ID],
                conf=self.confidence_threshold,
                verbose=False,
            )

            detections: list[dict[str, Any]] = []

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for i in range(len(boxes)):
                    # Get bounding box coordinates
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)

                    # Clamp coordinates to image bounds
                    x1 = max(0, min(x1, img_width - 1))
                    y1 = max(0, min(y1, img_height - 1))
                    x2 = max(0, min(x2, img_width - 1))
                    y2 = max(0, min(y2, img_height - 1))

                    # Skip invalid boxes
                    if x2 <= x1 or y2 <= y1:
                        logger.warning(
                            "invalid_bbox_skipped",
                            image_path=str(image_path),
                            bbox=[x1, y1, x2, y2],
                        )
                        continue

                    # Get confidence score
                    confidence = float(boxes.conf[i].cpu().numpy())

                    # Crop the detected region
                    cropped = img_array[y1:y2, x1:x2]

                    detection = {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": confidence,
                        "cropped_image": cropped,
                    }
                    detections.append(detection)

            logger.info(
                "detection_complete",
                image_path=str(image_path),
                detections_count=len(detections),
                confidences=[d["confidence"] for d in detections],
            )

            return detections

        except Exception as error:
            if isinstance(error, (ImageReadError, ImageProcessingError)):
                raise
            raise ImageProcessingError(
                f"Failed to detect players in image: {error}",
                str(image_path),
            )

    def detect_with_metadata(self, image_path: str | Path) -> dict[str, Any]:
        """
        Detect players and return results with additional metadata.

        Args:
            image_path: Path to the image file.

        Returns:
            Dictionary containing:
                - "detections": List of detection dicts (same as detect())
                - "image_path": Original image path
                - "image_size": (width, height) tuple
                - "total_detections": Number of detections
                - "max_confidence": Highest confidence score (or 0.0 if none)
                - "detector_available": Whether ultralytics was available

        Example:
            result = detector.detect_with_metadata("./images/game.jpg")
            print(f"Found {result['total_detections']} players")
            print(f"Best detection: {result['max_confidence']:.2f}")
        """
        image_path = Path(image_path)

        # Get image dimensions
        try:
            with Image.open(image_path) as img:
                img_width, img_height = img.size
        except Exception as error:
            raise ImageReadError(
                f"Cannot read image dimensions: {error}",
                str(image_path),
            )

        detections = self.detect(image_path)

        max_conf = max((d["confidence"] for d in detections), default=0.0)

        return {
            "detections": detections,
            "image_path": str(image_path),
            "image_size": (img_width, img_height),
            "total_detections": len(detections),
            "max_confidence": max_conf,
            "detector_available": self.is_available(),
        }
