"""Tests for the grading rubric."""

import unittest
from pathlib import Path

from src.analyzer import GradingRubric
from src.types.config import WeightsConfig


class TestGradingRubric(unittest.TestCase):
    """Test grading rubric functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.rubric = GradingRubric()
        cls.images_dir = Path(__file__).parent.parent / "images"

    def test_default_weights(self):
        """Test that default weights are valid."""
        weights = self.rubric.weights
        self.assertIsInstance(weights, WeightsConfig)
        self.assertTrue(weights.validate())

    def test_custom_weights(self):
        """Test creating rubric with custom weights."""
        custom_weights = {"resolution_clarity": 0.2, "composition": 0.2}
        rubric = GradingRubric(weights=custom_weights)
        self.assertEqual(rubric.weights.resolution_clarity, 0.2)

    def test_score_image_returns_valid_scores(self):
        """Test that scoring returns valid PhotoScore."""
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)

        self.assertGreaterEqual(score.resolution_clarity, 1.0)
        self.assertLessEqual(score.resolution_clarity, 10.0)
        self.assertGreaterEqual(score.overall_score, 1.0)
        self.assertLessEqual(score.overall_score, 10.0)

    def test_all_parameters_scored(self):
        """Test that all 10 parameters are scored."""
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)

        expected_params = [
            "resolution_clarity",
            "composition",
            "action_moment",
            "lighting",
            "color_quality",
            "subject_isolation",
            "emotional_impact",
            "technical_quality",
            "relevance",
            "instagram_suitability",
        ]

        for param in expected_params:
            value = getattr(score, param)
            self.assertGreaterEqual(value, 1.0, f"{param} should be >= 1.0")
            self.assertLessEqual(value, 10.0, f"{param} should be <= 10.0")

    def test_overall_score_is_weighted_average(self):
        """Test that overall score is a weighted average."""
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

    def test_relevance_defaults_to_five(self):
        """Test that relevance defaults to 5.0 without external context."""
        image_path = self.images_dir / "IMG_1409.jpeg"

        if not image_path.exists():
            self.skipTest(f"Test image not found: {image_path}")

        score = self.rubric.score_image(image_path)
        self.assertEqual(score.relevance, 5.0)

    def test_score_batch_images(self):
        """Test scoring multiple images."""
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
