from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from PIL import Image, ExifTags

from src.types.errors import ImageReadError
from src.types.photo import PhotoMetadata

if TYPE_CHECKING:
    from src.types.config import AnalysisConfig

logger = logging.getLogger(__name__)


class MetadataExtractor:
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config
        self._formats = (
            set(config.formats)
            if config
            else {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
        )

    @property
    def supported_formats(self) -> set[str]:
        return self._formats

    def extract(self, image_path: str | Path) -> PhotoMetadata:
        image_path = Path(image_path)

        if not image_path.exists():
            raise ImageReadError(f"Image file not found: {image_path}", str(image_path))

        if image_path.suffix.lower() not in self._formats:
            raise ImageReadError(
                f"Unsupported format: {image_path.suffix}", str(image_path)
            )

        try:
            with Image.open(image_path) as img:
                img.load()

                width, height = img.size
                format_name = img.format or "UNKNOWN"
                color_mode = img.mode
                file_size = os.path.getsize(image_path)

                exif_data = self._extract_exif(img)

                return PhotoMetadata(
                    path=str(image_path.absolute()),
                    filename=image_path.name,
                    width=width,
                    height=height,
                    format=format_name,
                    file_size=file_size,
                    color_mode=color_mode,
                    exif_data=exif_data,
                )

        except Exception as e:
            raise ImageReadError(f"Failed to read image: {e}", str(image_path))

    def _extract_exif(self, img: Image.Image) -> dict:
        exif_data = {}

        try:
            raw_exif = img.getexif()
            if raw_exif:
                for tag_id, value in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

                    if isinstance(value, bytes):
                        continue

                    if tag_name in ("MakerNote", "UserComment"):
                        continue

                    exif_data[tag_name] = self._normalize_exif_value(value)

        except Exception as e:
            logger.debug(f"Could not extract EXIF data: {e}")

        return exif_data

    def _normalize_exif_value(self, value: object) -> object:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, tuple):
            return [self._normalize_exif_value(item) for item in value]
        if isinstance(value, list):
            return [self._normalize_exif_value(item) for item in value]
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            denominator = getattr(value, "denominator", 1) or 1
            numerator = getattr(value, "numerator", 0)
            return float(numerator) / float(denominator)
        return str(value)

    def extract_batch(
        self, directory: str | Path, recursive: bool = True
    ) -> list[PhotoMetadata]:
        return list(self.iter_metadata(directory, recursive=recursive))

    def iter_metadata(
        self, directory: str | Path, recursive: bool = True
    ) -> Iterator[PhotoMetadata]:
        directory = Path(directory)

        if not directory.exists():
            raise ImageReadError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise ImageReadError(f"Not a directory: {directory}")

        pattern = "**/*" if recursive else "*"

        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self._formats:
                try:
                    yield self.extract(file_path)
                except ImageReadError as e:
                    logger.warning(f"Skipping {file_path}: {e}")
