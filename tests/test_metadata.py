"""Tests for metadata extraction."""

import unittest
from pathlib import Path

from src.analyzer import MetadataExtractor
from src.types.errors import ImageReadError


class TestMetadataExtractor(unittest.TestCase):
    """Test metadata extraction functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.extractor = MetadataExtractor()
        cls.images_dir = Path(__file__).parent.parent / "images"

    def test_extract_basic_metadata(self):
        """Test extracting basic metadata from an image."""
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        metadata = self.extractor.extract(image_path)

        self.assertEqual(metadata.filename, "IMG_1409.jpeg")
        self.assertGreater(metadata.width, 0)
        self.assertGreater(metadata.height, 0)
        self.assertEqual(metadata.format, "JPEG")
        self.assertGreater(metadata.file_size, 0)
        self.assertIn(metadata.color_mode, ("RGB", "RGBA", "L"))

    def test_extract_nonexistent_file_raises_error(self):
        """Test that extracting from nonexistent file raises error."""
        with self.assertRaises(ImageReadError):
            self.extractor.extract("/nonexistent/image.jpg")

    def test_extract_unsupported_format_raises_error(self):
        """Test that unsupported formats raise error."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an image")
            temp_path = f.name

        try:
            with self.assertRaises(ImageReadError):
                self.extractor.extract(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_extract_batch_from_directory(self):
        """Test batch extraction from images directory."""
        if not self.images_dir.exists():
            self.skipTest(f"Images directory not found: {self.images_dir}")

        results = self.extractor.extract_batch(self.images_dir, recursive=False)

        self.assertGreater(len(results), 0)

        for metadata in results:
            self.assertGreater(metadata.width, 0)
            self.assertGreater(metadata.height, 0)

    def test_aspect_ratio_calculation(self):
        """Test that aspect ratio is calculated correctly."""
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        metadata = self.extractor.extract(image_path)

        expected_ratio = metadata.width / metadata.height
        self.assertAlmostEqual(metadata.aspect_ratio, expected_ratio, places=3)


if __name__ == "__main__":
    unittest.main()
