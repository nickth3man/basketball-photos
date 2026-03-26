from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.analyzer.image_analyzer import ImageAnalyzer
from src.types.config import Config


class AnalysisPipelineTest(unittest.TestCase):
    def test_analyze_directory_returns_results(self) -> None:
        # TODO: Add coverage for recursive discovery, persist=False behavior,
        # and empty directories so pipeline orchestration stays predictable.
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


if __name__ == "__main__":
    unittest.main()
