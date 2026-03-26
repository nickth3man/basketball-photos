from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from src.analyzer.image_analyzer import ImageAnalyzer
from src.types.config import Config


class AnalysisPipelineTest(unittest.TestCase):
    def test_analyze_directory_returns_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "sample.jpg"
            Image.new("RGB", (1600, 1200), color=(120, 80, 200)).save(image_path)

            config = Config()
            config.output.database = str(root / "data" / "photo_grades.db")
            config.output.reports_dir = str(root / "reports")
            analyzer = ImageAnalyzer(config)

            results = analyzer.analyze_directory(root, recursive=False, persist=True)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].metadata.filename, "sample.jpg")
            self.assertGreaterEqual(results[0].scores.overall_score, 1.0)
            self.assertTrue((root / "reports" / "analysis_results.json").exists())

    def test_analyze_directory_supports_recursive_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            Image.new("RGB", (1600, 1200), color=(10, 20, 30)).save(
                nested / "nested.jpg"
            )

            config = Config()
            config.output.database = str(root / "data" / "photo_grades.db")
            config.output.reports_dir = str(root / "reports")
            analyzer = ImageAnalyzer(config)

            self.assertEqual(
                analyzer.analyze_directory(root, recursive=False, persist=False), []
            )

            recursive_results = analyzer.analyze_directory(
                root, recursive=True, persist=False
            )

            self.assertEqual(len(recursive_results), 1)
            self.assertEqual(recursive_results[0].metadata.filename, "nested.jpg")

    def test_analyze_directory_can_skip_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            Image.new("RGB", (1600, 1200), color=(120, 80, 200)).save(
                root / "sample.jpg"
            )

            config = Config()
            config.output.database = str(root / "data" / "photo_grades.db")
            config.output.reports_dir = str(root / "reports")
            analyzer = ImageAnalyzer(config)

            results = analyzer.analyze_directory(root, recursive=False, persist=False)

            self.assertEqual(len(results), 1)
            self.assertFalse((root / "reports" / "analysis_results.json").exists())
            self.assertFalse((root / "data" / "photo_grades.db").exists())

    def test_analyze_directory_returns_empty_for_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = Config()
            config.output.database = str(root / "data" / "photo_grades.db")
            config.output.reports_dir = str(root / "reports")
            analyzer = ImageAnalyzer(config)

            self.assertEqual(
                analyzer.analyze_directory(root, recursive=False, persist=False), []
            )

    def test_analyze_directory_reports_parallel_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for index in range(3):
                Image.new("RGB", (1600, 1200), color=(120, 80 + index, 200)).save(
                    root / f"sample-{index}.jpg"
                )

            config = Config()
            config.output.database = str(root / "data" / "photo_grades.db")
            config.output.reports_dir = str(root / "reports")
            analyzer = ImageAnalyzer(config)
            progress_callback = MagicMock()

            results = analyzer.analyze_directory(
                root,
                recursive=False,
                persist=False,
                parallel=True,
                max_workers=2,
                progress_callback=progress_callback,
            )

            self.assertEqual(len(results), 3)
            self.assertEqual(progress_callback.call_count, 3)
            self.assertEqual(progress_callback.call_args_list[-1].args, (3, 3))


if __name__ == "__main__":
    unittest.main()
