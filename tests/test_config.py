"""Tests for configuration loading."""

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from src.config import load_config, get_default_config_path
from src.config.loader import _substitute_env_vars
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


class TestEnvVarSubstitution(unittest.TestCase):
    """Test environment variable substitution in config."""

    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_substitute_simple_env_var(self):
        os.environ["TEST_PATH"] = "/custom/path"
        result = _substitute_env_vars("${TEST_PATH}")
        self.assertEqual(result, "/custom/path")

    def test_substitute_env_var_without_braces(self):
        os.environ["TEST_VAR"] = "value"
        result = _substitute_env_vars("$TEST_VAR")
        self.assertEqual(result, "value")

    def test_substitute_missing_env_var_returns_empty(self):
        result = _substitute_env_vars("${NONEXISTENT_VAR}")
        self.assertEqual(result, "")

    def test_substitute_with_default_value(self):
        result = _substitute_env_vars("${MISSING_VAR:-default_value}")
        self.assertEqual(result, "default_value")

    def test_substitute_existing_var_ignores_default(self):
        os.environ["EXISTING_VAR"] = "actual_value"
        result = _substitute_env_vars("${EXISTING_VAR:-default_value}")
        self.assertEqual(result, "actual_value")

    def test_substitute_nested_dict(self):
        os.environ["DB_PATH"] = "/data/db.sqlite"
        os.environ["REPORTS_DIR"] = "/reports"
        data = {
            "output": {
                "database": "${DB_PATH}",
                "reports_dir": "${REPORTS_DIR}",
            }
        }
        result = _substitute_env_vars(data)
        self.assertEqual(result["output"]["database"], "/data/db.sqlite")
        self.assertEqual(result["output"]["reports_dir"], "/reports")

    def test_substitute_list_values(self):
        os.environ["CATEGORY"] = "action_shot"
        data = {"categories": ["${CATEGORY}", "portrait"]}
        result = _substitute_env_vars(data)
        self.assertEqual(result["categories"][0], "action_shot")

    def test_substitute_preserves_non_string_values(self):
        data = {
            "min_width": 1920,
            "enabled": True,
            "ratio": 1.5,
        }
        result = _substitute_env_vars(data)
        self.assertEqual(result["min_width"], 1920)
        self.assertEqual(result["enabled"], True)
        self.assertEqual(result["ratio"], 1.5)

    def test_load_config_with_env_vars(self):
        os.environ["CUSTOM_REPORTS_DIR"] = "/custom/reports"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "output": {
                        "reports_dir": "${CUSTOM_REPORTS_DIR}",
                    }
                },
                f,
            )
            temp_path = f.name

        try:
            config = load_config(temp_path)
            self.assertEqual(config.output.reports_dir, "/custom/reports")
        finally:
            Path(temp_path).unlink()
            del os.environ["CUSTOM_REPORTS_DIR"]


if __name__ == "__main__":
    unittest.main()
