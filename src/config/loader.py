import logging
from pathlib import Path
from typing import Any

import yaml

from src.types.config import Config
from src.types.errors import ConfigError

logger = logging.getLogger(__name__)


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return Path(__file__).parent.parent.parent / "config" / "settings.yaml"


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, uses default path.

    Returns:
        Config object with loaded settings

    Raises:
        ConfigError: If configuration is invalid or file cannot be read
    """
    if config_path is None:
        config_path = get_default_config_path()
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return _get_default_config()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}", str(config_path))
    except OSError as e:
        raise ConfigError(f"Cannot read config file: {e}", str(config_path))

    config = Config.from_dict(data)

    issues = config.validate()
    if issues:
        for issue in issues:
            logger.warning(f"Config validation issue: {issue}")

    if not config.weights.validate():
        logger.warning(
            f"Weights sum to {sum(config.weights.to_dict().values()):.3f}, "
            "expected ~1.0. Scores may be skewed."
        )

    logger.info(f"Loaded configuration from {config_path}")
    return config


def _get_default_config() -> Config:
    """Get default configuration when config file is missing."""
    logger.info("Using default configuration")
    return Config()


def save_config(config: Config, output_path: str | Path) -> None:
    """Save configuration to YAML file.

    Args:
        config: Config object to save
        output_path: Path to save configuration file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.to_dict()

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved configuration to {output_path}")
