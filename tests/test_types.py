"""Tests for core types and dataclasses."""

import unittest
from datetime import datetime

from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore
from src.types.analysis import AnalysisResult
from src.types.config import Config, WeightsConfig, AnalysisConfig, ThresholdsConfig
from src.types.errors import AnalysisError, ImageReadError, ConfigError


class TestPhotoMetadata(unittest.TestCase):
    """Test PhotoMetadata dataclass."""

    def test_basic_metadata_creation(self):
        """Test creating basic photo metadata."""
        metadata = PhotoMetadata(
            path="/path/to/image.jpg",
            filename="image.jpg",
            width=1920,
            height=1080,
            format="JPEG",
            file_size=500000,
            color_mode="RGB",
        )

        self.assertEqual(metadata.path, "/path/to/image.jpg")
        self.assertEqual(metadata.width, 1920)
        self.assertEqual(metadata.height, 1080)
        self.assertAlmostEqual(metadata.aspect_ratio, 1920 / 1080, places=3)
        self.assertEqual(metadata.megapixels, 2.0736)
        self.assertTrue(metadata.is_landscape)
        self.assertFalse(metadata.is_portrait)
        self.assertFalse(metadata.is_square)

    def test_square_image(self):
        """Test square image detection."""
        metadata = PhotoMetadata(
            path="/path/to/square.jpg",
            filename="square.jpg",
            width=1080,
            height=1080,
            format="JPEG",
            file_size=300000,
            color_mode="RGB",
        )

        self.assertTrue(metadata.is_square)
        self.assertAlmostEqual(metadata.aspect_ratio, 1.0, places=3)

    def test_portrait_image(self):
        """Test portrait image detection."""
        metadata = PhotoMetadata(
            path="/path/to/portrait.jpg",
            filename="portrait.jpg",
            width=1080,
            height=1920,
            format="JPEG",
            file_size=400000,
            color_mode="RGB",
        )

        self.assertTrue(metadata.is_portrait)
        self.assertFalse(metadata.is_landscape)

    def test_resolution_tiers(self):
        """Test resolution tier categorization."""
        test_cases = [
            (4000, 3000, "ultra"),  # 12 MP
            (3000, 3000, "high"),  # 9 MP
            (2000, 2000, "medium"),  # 4 MP
            (1500, 1500, "low"),  # 2.25 MP
            (800, 600, "minimal"),  # 0.48 MP
        ]

        for width, height, expected_tier in test_cases:
            metadata = PhotoMetadata(
                path="/path/to/image.jpg",
                filename="image.jpg",
                width=width,
                height=height,
                format="JPEG",
                file_size=100000,
                color_mode="RGB",
            )
            self.assertEqual(metadata.resolution_tier, expected_tier)

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = PhotoMetadata(
            path="/path/to/image.jpg",
            filename="image.jpg",
            width=1920,
            height=1080,
            format="JPEG",
            file_size=500000,
            color_mode="RGB",
            exif_data={"camera": "Canon"},
        )

        data = original.to_dict()
        restored = PhotoMetadata.from_dict(data)

        self.assertEqual(restored.path, original.path)
        self.assertEqual(restored.width, original.width)
        self.assertEqual(restored.exif_data, original.exif_data)


class TestPhotoScore(unittest.TestCase):
    """Test PhotoScore dataclass."""

    def test_basic_score_creation(self):
        """Test creating basic photo scores."""
        weights = {
            "resolution_clarity": 0.12,
            "composition": 0.12,
            "action_moment": 0.15,
            "lighting": 0.10,
            "color_quality": 0.08,
            "subject_isolation": 0.10,
            "emotional_impact": 0.13,
            "technical_quality": 0.10,
            "relevance": 0.05,
            "instagram_suitability": 0.05,
        }

        score = PhotoScore(
            resolution_clarity=8.0,
            composition=7.5,
            action_moment=9.0,
            lighting=8.5,
            color_quality=7.0,
            subject_isolation=6.5,
            emotional_impact=8.0,
            technical_quality=7.5,
            relevance=5.0,
            instagram_suitability=6.0,
            weights=weights,
        )

        self.assertEqual(score.resolution_clarity, 8.0)
        self.assertTrue(1.0 <= score.overall_score <= 10.0)
        self.assertEqual(len(score.weights), 10)

    def test_overall_score_calculation(self):
        """Test weighted overall score calculation."""
        weights = {
            k: 0.1
            for k in [
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
        }

        score = PhotoScore(
            resolution_clarity=5.0,
            composition=5.0,
            action_moment=5.0,
            lighting=5.0,
            color_quality=5.0,
            subject_isolation=5.0,
            emotional_impact=5.0,
            technical_quality=5.0,
            relevance=5.0,
            instagram_suitability=5.0,
            weights=weights,
        )

        self.assertEqual(score.overall_score, 5.0)

    def test_grade_assignment(self):
        """Test letter grade assignment."""
        test_cases = [
            (9.5, "A+"),
            (8.7, "A"),
            (8.2, "A-"),
            (7.7, "B+"),
            (7.2, "B"),
            (6.7, "B-"),
            (6.2, "C+"),
            (5.7, "C"),
            (5.2, "C-"),
            (4.5, "D"),
            (3.0, "F"),
        ]

        for overall, expected_grade in test_cases:
            score = PhotoScore(
                resolution_clarity=overall,
                composition=overall,
                action_moment=overall,
                lighting=overall,
                color_quality=overall,
                subject_isolation=overall,
                emotional_impact=overall,
                technical_quality=overall,
                relevance=overall,
                instagram_suitability=overall,
            )
            self.assertEqual(score.grade, expected_grade)

    def test_quality_tier(self):
        """Test quality tier assignment."""
        test_cases = [
            (9.5, "excellent"),
            (8.0, "good"),
            (6.5, "acceptable"),
            (4.5, "poor"),
            (3.0, "unacceptable"),
        ]

        for overall, expected_tier in test_cases:
            score = PhotoScore(
                resolution_clarity=overall,
                composition=overall,
                action_moment=overall,
                lighting=overall,
                color_quality=overall,
                subject_isolation=overall,
                emotional_impact=overall,
                technical_quality=overall,
                relevance=overall,
                instagram_suitability=overall,
            )
            self.assertEqual(score.quality_tier, expected_tier)

    def test_score_validation(self):
        """Test that invalid scores raise ValueError."""
        with self.assertRaises(ValueError):
            PhotoScore(
                resolution_clarity=11.0,  # Invalid: > 10
                composition=5.0,
                action_moment=5.0,
                lighting=5.0,
                color_quality=5.0,
                subject_isolation=5.0,
                emotional_impact=5.0,
                technical_quality=5.0,
                relevance=5.0,
                instagram_suitability=5.0,
            )

    def test_top_and_bottom_params(self):
        """Test identifying top and bottom scoring parameters."""
        score = PhotoScore(
            resolution_clarity=9.0,  # Top
            composition=5.0,
            action_moment=8.5,  # Top
            lighting=3.0,  # Bottom
            color_quality=7.0,
            subject_isolation=8.0,  # Top
            emotional_impact=4.0,  # Bottom
            technical_quality=6.0,
            relevance=2.0,  # Bottom
            instagram_suitability=6.5,
        )

        top = score.top_three_params
        bottom = score.bottom_three_params

        self.assertEqual(top[0][0], "resolution_clarity")
        self.assertEqual(bottom[0][0], "relevance")


class TestConfig(unittest.TestCase):
    """Test Config and related dataclasses."""

    def test_default_config(self):
        """Test creating config with defaults."""
        config = Config()

        self.assertEqual(config.analysis.min_width, 1080)
        self.assertEqual(config.analysis.min_height, 1080)
        self.assertEqual(len(config.categories), 10)

    def test_weights_validation(self):
        """Test that weights sum to 1.0."""
        weights = WeightsConfig()
        self.assertTrue(weights.validate())

    def test_config_validation(self):
        """Test config validation."""
        config = Config()
        issues = config.validate()
        self.assertEqual(len(issues), 0)

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "analysis": {
                "min_width": 1920,
                "min_height": 1080,
            },
            "weights": {
                "resolution_clarity": 0.15,
                "composition": 0.15,
            },
            "categories": ["action_shot", "portrait"],
        }

        config = Config.from_dict(data)

        self.assertEqual(config.analysis.min_width, 1920)
        self.assertEqual(config.analysis.min_height, 1080)
        self.assertEqual(config.weights.resolution_clarity, 0.15)
        self.assertEqual(len(config.categories), 2)

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = Config()
        data = config.to_dict()

        self.assertIn("analysis", data)
        self.assertIn("weights", data)
        self.assertIn("categories", data)
        self.assertEqual(data["analysis"]["min_width"], 1080)


class TestErrors(unittest.TestCase):
    """Test custom exceptions."""

    def test_analysis_error(self):
        """Test AnalysisError with image path."""
        error = AnalysisError("Test error", image_path="/path/to/image.jpg")
        self.assertIn("Test error", str(error))
        self.assertIn("/path/to/image.jpg", str(error))

    def test_image_read_error(self):
        """Test ImageReadError."""
        error = ImageReadError("Cannot read image", image_path="/bad/path.jpg")
        self.assertIn("Cannot read image", str(error))

    def test_config_error(self):
        """Test ConfigError."""
        error = ConfigError("Invalid config", config_path="/config/settings.yaml")
        self.assertIn("Invalid config", str(error))
        self.assertIn("/config/settings.yaml", str(error))


if __name__ == "__main__":
    unittest.main()
