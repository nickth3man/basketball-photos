"""Photo metadata dataclass for storing image properties."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class PhotoMetadata:
    """Metadata extracted from a photo file.

    Attributes:
        path: Absolute path to the image file
        filename: Name of the file (with extension)
        width: Image width in pixels
        height: Image height in pixels
        format: Image format (JPEG, PNG, WEBP, etc.)
        file_size: File size in bytes
        color_mode: PIL color mode (RGB, RGBA, L, etc.)
        aspect_ratio: Width divided by height
        exif_data: Dictionary of EXIF metadata if available
        created_at: Timestamp when this metadata was extracted
    """

    path: str
    filename: str
    width: int
    height: int
    format: str
    file_size: int
    color_mode: str
    aspect_ratio: float = field(init=False)
    exif_data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Calculate derived fields after initialization."""
        if self.height > 0:
            self.aspect_ratio = self.width / self.height
        else:
            self.aspect_ratio = 0.0

    @property
    def megapixels(self) -> float:
        """Return total megapixels (width * height / 1,000,000)."""
        return (self.width * self.height) / 1_000_000

    @property
    def is_square(self) -> bool:
        """Check if image is approximately square (aspect ratio 0.95-1.05)."""
        return 0.95 <= self.aspect_ratio <= 1.05

    @property
    def is_landscape(self) -> bool:
        """Check if image is in landscape orientation."""
        return self.aspect_ratio > 1.05

    @property
    def is_portrait(self) -> bool:
        """Check if image is in portrait orientation."""
        return self.aspect_ratio < 0.95

    @property
    def resolution_tier(self) -> str:
        """Categorize resolution into tiers."""
        mp = self.megapixels
        if mp >= 12:
            return "ultra"
        elif mp >= 8:
            return "high"
        elif mp >= 4:
            return "medium"
        elif mp >= 2:
            return "low"
        else:
            return "minimal"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "file_size": self.file_size,
            "color_mode": self.color_mode,
            "aspect_ratio": self.aspect_ratio,
            "megapixels": self.megapixels,
            "exif_data": self.exif_data,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhotoMetadata":
        """Create PhotoMetadata from dictionary."""
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        calculated_fields = [
            "aspect_ratio",
            "megapixels",
            "is_square",
            "is_landscape",
            "is_portrait",
            "resolution_tier",
        ]
        for field in calculated_fields:
            data.pop(field, None)
        return cls(**data)
