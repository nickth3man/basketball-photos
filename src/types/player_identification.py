"""Player identification dataclasses for detection and recognition results."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlayerIdentity:
    """Identity information for a detected player in a photo.

    Combines detection, OCR, and identification results with confidence scores.

    Attributes:
        player_id: NBA.com player ID (0 if unknown/unmatched)
        name: Full player name (empty string if unknown)
        jersey_number: Jersey number as string (e.g., "23", "0")
        team: Team name (e.g., "Los Angeles Lakers")
        confidence: Overall identification confidence (0.0-1.0)
        detection_confidence: YOLO person detection confidence (0.0-1.0)
        ocr_confidence: EasyOCR jersey recognition confidence (0.0-1.0)
        bbox: Bounding box [x1, y1, x2, y2] in image coordinates
        review_status: "auto_approved", "needs_review", or "rejected"
        method: Identification method used ("jersey_ocr", "face_recognition", "combined")
    """

    player_id: int
    name: str
    jersey_number: str
    team: str
    confidence: float
    detection_confidence: float
    ocr_confidence: float
    bbox: list[int] = field(default_factory=list)
    review_status: str = "needs_review"
    method: str = "jersey_ocr"

    def __post_init__(self) -> None:
        """Validate confidence ranges and set review status after initialization."""
        self._validate_confidence(self.confidence, "confidence")
        self._validate_confidence(self.detection_confidence, "detection_confidence")
        self._validate_confidence(self.ocr_confidence, "ocr_confidence")
        self._validate_bbox()
        self._validate_review_status()
        self._validate_method()
        if self.review_status == "needs_review":
            self.review_status = self.identification_tier

    def _validate_confidence(self, value: float, field_name: str) -> None:
        """Ensure confidence value is within valid range (0.0-1.0)."""
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0, got {value}")

    def _validate_bbox(self) -> None:
        """Ensure bounding box has exactly 4 integer coordinates."""
        if self.bbox and len(self.bbox) != 4:
            raise ValueError(
                f"bbox must have exactly 4 coordinates [x1, y1, x2, y2], got {len(self.bbox)}"
            )

    def _validate_review_status(self) -> None:
        """Ensure review_status is a valid value."""
        valid_statuses = {"auto_approved", "needs_review", "rejected"}
        if self.review_status not in valid_statuses:
            raise ValueError(
                f"review_status must be one of {valid_statuses}, got '{self.review_status}'"
            )

    def _validate_method(self) -> None:
        """Ensure method is a valid value."""
        valid_methods = {"jersey_ocr", "face_recognition", "combined"}
        if self.method not in valid_methods:
            raise ValueError(
                f"method must be one of {valid_methods}, got '{self.method}'"
            )

    @property
    def is_high_confidence(self) -> bool:
        """Check if identification has high confidence (>=0.85)."""
        return self.confidence >= 0.85

    @property
    def needs_review(self) -> bool:
        """Check if identification needs manual review (0.60 <= confidence < 0.85)."""
        return 0.60 <= self.confidence < 0.85

    @property
    def identification_tier(self) -> str:
        """Return identification tier based on confidence thresholds.

        Returns:
            "auto_approved" if confidence >= 0.85
            "needs_review" if 0.60 <= confidence < 0.85
            "rejected" if confidence < 0.60
        """
        if self.confidence >= 0.85:
            return "auto_approved"
        elif self.confidence >= 0.60:
            return "needs_review"
        else:
            return "rejected"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Ensures bbox is a list (not numpy array) for JSON compatibility.
        """
        return {
            "player_id": self.player_id,
            "name": self.name,
            "jersey_number": self.jersey_number,
            "team": self.team,
            "confidence": self.confidence,
            "detection_confidence": self.detection_confidence,
            "ocr_confidence": self.ocr_confidence,
            "bbox": list(self.bbox),
            "review_status": self.review_status,
            "method": self.method,
            "is_high_confidence": self.is_high_confidence,
            "needs_review": self.needs_review,
            "identification_tier": self.identification_tier,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerIdentity":
        """Create PlayerIdentity from dictionary.

        Args:
            data: Dictionary containing player identity data

        Returns:
            PlayerIdentity instance

        Note:
            Computed properties (is_high_confidence, needs_review, identification_tier)
            are removed from data if present, as they are calculated from confidence.
        """
        data = data.copy()
        data.pop("is_high_confidence", None)
        data.pop("needs_review", None)
        data.pop("identification_tier", None)

        return cls(**data)


@dataclass
class PlayerDetectionResult:
    """Batch processing result for player detections in a single photo.

    Contains all detected players along with aggregate statistics.

    Attributes:
        photo_path: Path to the analyzed photo
        photo_id: Database ID of the photo (0 if not persisted)
        detections: List of PlayerIdentity objects for each detected player
        total_detections: Total number of players detected
        high_confidence_count: Number of high confidence (>=0.85) identifications
        review_required_count: Number of identifications needing review
        processing_time_ms: Time taken for detection in milliseconds
        model_version: Version of detection/recognition model used
        errors: List of any errors encountered during processing
    """

    photo_path: str
    photo_id: int
    detections: list[PlayerIdentity] = field(default_factory=list)
    total_detections: int = field(init=False)
    high_confidence_count: int = field(init=False)
    review_required_count: int = field(init=False)
    processing_time_ms: float = 0.0
    model_version: str = "1.0.0"
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Calculate aggregate statistics after initialization."""
        self.total_detections = len(self.detections)
        self.high_confidence_count = sum(
            1 for d in self.detections if d.is_high_confidence
        )
        self.review_required_count = sum(1 for d in self.detections if d.needs_review)

    @property
    def auto_approved_count(self) -> int:
        """Number of auto-approved identifications."""
        return self.high_confidence_count

    @property
    def rejected_count(self) -> int:
        """Number of rejected (low confidence) identifications."""
        return sum(1 for d in self.detections if d.identification_tier == "rejected")

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during processing."""
        return len(self.errors) > 0

    @property
    def all_high_confidence(self) -> bool:
        """Check if all detections are high confidence."""
        return (
            self.total_detections > 0
            and self.high_confidence_count == self.total_detections
        )

    @property
    def needs_any_review(self) -> bool:
        """Check if any detection requires manual review."""
        return self.review_required_count > 0 or self.rejected_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "photo_path": self.photo_path,
            "photo_id": self.photo_id,
            "detections": [d.to_dict() for d in self.detections],
            "total_detections": self.total_detections,
            "high_confidence_count": self.high_confidence_count,
            "review_required_count": self.review_required_count,
            "auto_approved_count": self.auto_approved_count,
            "rejected_count": self.rejected_count,
            "processing_time_ms": self.processing_time_ms,
            "model_version": self.model_version,
            "errors": self.errors,
            "has_errors": self.has_errors,
            "all_high_confidence": self.all_high_confidence,
            "needs_any_review": self.needs_any_review,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerDetectionResult":
        """Create PlayerDetectionResult from dictionary.

        Args:
            data: Dictionary containing detection result data

        Returns:
            PlayerDetectionResult instance
        """
        detections_data = data.get("detections", [])
        detections = [PlayerIdentity.from_dict(d) for d in detections_data]

        data = data.copy()
        data.pop("detections", None)
        data.pop("total_detections", None)
        data.pop("high_confidence_count", None)
        data.pop("review_required_count", None)
        data.pop("auto_approved_count", None)
        data.pop("rejected_count", None)
        data.pop("has_errors", None)
        data.pop("all_high_confidence", None)
        data.pop("needs_any_review", None)

        return cls(detections=detections, **data)
