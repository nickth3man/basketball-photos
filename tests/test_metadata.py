"""Tests for metadata extraction."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from src.analyzer import MetadataExtractor
from src.types.errors import ImageReadError


class TestMetadataExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extractor = MetadataExtractor()
        cls.images_dir = Path(__file__).parent.parent / "images"

    def test_extract_basic_metadata(self):
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
        with self.assertRaises(ImageReadError):
            self.extractor.extract("/nonexistent/image.jpg")

    def test_extract_unsupported_format_raises_error(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as file_handle:
            file_handle.write(b"not an image")
            temp_path = file_handle.name

        try:
            with self.assertRaises(ImageReadError):
                self.extractor.extract(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_extract_batch_from_directory(self):
        if not self.images_dir.exists():
            self.skipTest(f"Images directory not found: {self.images_dir}")

        results = self.extractor.extract_batch(self.images_dir, recursive=False)

        self.assertGreater(len(results), 0)
        for metadata in results:
            self.assertGreater(metadata.width, 0)
            self.assertGreater(metadata.height, 0)

    def test_aspect_ratio_calculation(self):
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        metadata = self.extractor.extract(image_path)

        self.assertAlmostEqual(
            metadata.aspect_ratio, metadata.width / metadata.height, places=3
        )

    def test_extract_batch_can_recurse_into_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            Image.new("RGB", (1280, 720), color=(20, 30, 40)).save(
                nested / "nested.jpg"
            )

            self.assertEqual(self.extractor.extract_batch(root, recursive=False), [])

            recursive = self.extractor.extract_batch(root, recursive=True)
            self.assertEqual(len(recursive), 1)
            self.assertEqual(recursive[0].filename, "nested.jpg")

    def test_iter_metadata_streams_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for index in range(2):
                Image.new("RGB", (640, 640), color=(index, 10, 20)).save(
                    root / f"sample-{index}.jpg"
                )

            streamed = list(self.extractor.iter_metadata(root, recursive=False))

            self.assertEqual(len(streamed), 2)
            self.assertTrue(all(item.filename.endswith(".jpg") for item in streamed))

    def test_extract_exif_normalizes_rational_values_and_skips_binary(self):
        rational = MagicMock(numerator=3, denominator=2)
        fake_image = MagicMock()
        fake_image.getexif.return_value = {
            33434: rational,
            37500: b"skip-me",
            271: "CameraBrand",
        }

        exif = self.extractor._extract_exif(fake_image)

        self.assertEqual(exif["ExposureTime"], 1.5)
        self.assertEqual(exif["Make"], "CameraBrand")
        self.assertNotIn("37500", exif)

    def test_extract_exif_handles_corrupt_payloads(self):
        fake_image = MagicMock()
        fake_image.getexif.side_effect = ValueError("corrupt exif")

        self.assertEqual(self.extractor._extract_exif(fake_image), {})


if __name__ == "__main__":
    unittest.main()
