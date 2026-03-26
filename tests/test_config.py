"""Tests for configuration loading."""

import tempfile
import unittest
from pathlib import Path

import yaml

from src.config import load_config, get_default_config_path
from src.types.config import Config
from src.types.errors import ConfigError


class TestConfigLoader(unittest.TestCase):
    """Test configuration loading functionality."""

    def test_get_default_config_path(self):
        """Test default config path resolution."""
        path = get_default_config_path()
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "settings.yaml")
        self.assertIn("config", path.parts)

    def test_load_default_config(self):
        """Test loading the actual settings.yaml file."""
        config = load_config()

        self.assertIsInstance(config, Config)
        self.assertEqual(config.analysis.min_width, 1080)
        self.assertEqual(config.analysis.min_height, 1080)
        self.assertTrue(config.weights.validate())

    def test_load_config_from_file(self):
        """Test loading config from a specific file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "analysis": {"min_width": 1920, "min_height": 1080},
                    "weights": {"resolution_clarity": 0.2, "composition": 0.2},
                    "categories": ["action_shot", "portrait"],
                },
                f,
            )
            temp_path = f.name

        try:
            config = load_config(temp_path)
            self.assertEqual(config.analysis.min_width, 1920)
            self.assertEqual(len(config.categories), 2)
        finally:
            Path(temp_path).unlink()

    def test_load_missing_file_uses_defaults(self):
        """Test that missing config file returns defaults."""
        config = load_config("/nonexistent/path/config.yaml")

        self.assertIsInstance(config, Config)
        self.assertEqual(config.analysis.min_width, 1080)

    def test_load_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises ConfigError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name

        try:
            with self.assertRaises(ConfigError):
                load_config(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_weights_validation(self):
        """Test that loaded weights are validated."""
        config = load_config()
        self.assertTrue(config.weights.validate())

        weights_sum = sum(config.weights.to_dict().values())
        self.assertAlmostEqual(weights_sum, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
