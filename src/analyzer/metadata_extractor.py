import logging
import os
from pathlib import Path

from PIL import Image, ExifTags

from src.types.errors import ImageReadError
from src.types.photo import PhotoMetadata

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract metadata from image files using Pillow."""

    # TODO: Keep this list aligned with config-level accepted formats so the
    # analyzer and discovery pipeline do not drift on supported file types.
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}

    def extract(self, image_path: str | Path) -> PhotoMetadata:
        """Extract metadata from an image file.

        Args:
            image_path: Path to the image file

        Returns:
            PhotoMetadata with extracted information

        Raises:
            ImageReadError: If the image cannot be read or is not a valid image
        """
        image_path = Path(image_path)

        if not image_path.exists():
            raise ImageReadError(f"Image file not found: {image_path}", str(image_path))

        if image_path.suffix.lower() not in self.SUPPORTED_FORMATS:
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
        """Extract EXIF data from an image.

        Args:
            img: PIL Image object

        Returns:
            Dictionary of EXIF tags and values
        """
        # TODO: Add coverage for rational values, corrupt EXIF payloads, and
        # skipped tags so metadata regressions are caught without real cameras.
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
        """Extract metadata from all images in a directory.

        Args:
            directory: Path to directory containing images
            recursive: Whether to search subdirectories

        Returns:
            List of PhotoMetadata for each valid image found
        """
        directory = Path(directory)

        if not directory.exists():
            raise ImageReadError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise ImageReadError(f"Not a directory: {directory}")

        # TODO: Offer a generator-based variant for larger imports so callers
        # can stream metadata instead of materializing every record at once.
        results = []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in directory.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_FORMATS
            ):
                try:
                    metadata = self.extract(file_path)
                    results.append(metadata)
                except ImageReadError as e:
                    logger.warning(f"Skipping {file_path}: {e}")

        return results
