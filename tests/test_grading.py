"""Tests for the grading rubric."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.analyzer import GradingRubric
from src.types.config import AnalysisConfig, WeightsConfig
from src.types.errors import ImageReadError


class TestGradingRubric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric = GradingRubric()
        cls.images_dir = Path(__file__).parent.parent / "images"

    def test_default_weights(self):
        weights = self.rubric.weights
        self.assertIsInstance(weights, WeightsConfig)
        self.assertTrue(weights.validate())

    def test_custom_weights(self):
        custom_weights = {"resolution_clarity": 0.2, "composition": 0.2}
        rubric = GradingRubric(weights=custom_weights)
        self.assertEqual(rubric.weights.resolution_clarity, 0.2)

    def test_score_image_returns_valid_scores(self):
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)

        self.assertGreaterEqual(score.resolution_clarity, 1.0)
        self.assertLessEqual(score.resolution_clarity, 10.0)
        self.assertGreaterEqual(score.overall_score, 1.0)
        self.assertLessEqual(score.overall_score, 10.0)

    def test_relevance_defaults_to_five(self):
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)
        self.assertEqual(score.relevance, 5.0)

    def test_overall_score_is_weighted_average(self):
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)

        weights = score.weights
        expected = (
            score.resolution_clarity * weights.get("resolution_clarity", 0.1)
            + score.composition * weights.get("composition", 0.1)
            + score.action_moment * weights.get("action_moment", 0.1)
            + score.lighting * weights.get("lighting", 0.1)
            + score.color_quality * weights.get("color_quality", 0.1)
            + score.subject_isolation * weights.get("subject_isolation", 0.1)
            + score.emotional_impact * weights.get("emotional_impact", 0.1)
            + score.technical_quality * weights.get("technical_quality", 0.1)
            + score.relevance * weights.get("relevance", 0.1)
            + score.instagram_suitability * weights.get("instagram_suitability", 0.1)
        )

        self.assertAlmostEqual(score.overall_score, round(expected, 2), places=1)

    def test_clamp_score_enforces_range(self):
        self.assertEqual(self.rubric._clamp_score(12.4), 10.0)
        self.assertEqual(self.rubric._clamp_score(0.2), 1.0)
        self.assertEqual(self.rubric._clamp_score(7.26), 7.3)

    def test_private_relevance_helper_uses_context_keywords(self):
        self.assertEqual(self.rubric._score_relevance("nba finals celebration"), 5.5)
        self.assertEqual(self.rubric._score_relevance(None), 5.0)

    def test_private_instagram_helper_rewards_square_images(self):
        square_score = self.rubric._score_instagram_suitability(
            Image.new("RGB", (1080, 1080))
        )
        portrait_score = self.rubric._score_instagram_suitability(
            Image.new("RGB", (1080, 1350))
        )

        self.assertGreaterEqual(square_score, portrait_score)

    def test_private_lighting_helper_returns_valid_range(self):
        score = self.rubric._score_lighting(np.full((32, 32), 128.0))

        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)

    def test_score_image_rejects_images_above_pixel_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "too-many-pixels.jpg"
            Image.new("RGB", (20, 20), color=(10, 20, 30)).save(image_path)
            rubric = GradingRubric(
                analysis_config=AnalysisConfig(max_image_pixels=100, max_image_mb=10)
            )

            with self.assertRaises(ImageReadError):
                rubric.score_image(image_path)

    def test_score_image_rejects_images_above_size_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "too-large.jpg"
            Image.new("RGB", (20, 20), color=(10, 20, 30)).save(image_path)
            rubric = GradingRubric(
                analysis_config=AnalysisConfig(max_image_pixels=10_000, max_image_mb=0)
            )

            with self.assertRaises(ImageReadError):
                rubric.score_image(image_path)

    def test_score_batch_images(self):
        if not self.images_dir.exists():
            self.skipTest(f"Images directory not found: {self.images_dir}")

        image_files = list(self.images_dir.glob("*.jpeg"))[:3]

        if not image_files:
            self.skipTest("No test images found")

        for image_path in image_files:
            score = self.rubric.score_image(image_path)
            self.assertGreaterEqual(score.overall_score, 1.0)


if __name__ == "__main__":
    unittest.main()
