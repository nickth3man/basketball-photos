"""Core types and dataclasses for photo analysis."""

from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore
from src.types.analysis import AnalysisResult
from src.types.config import (
    Config,
    AnalysisConfig,
    WeightsConfig,
    ThresholdsConfig,
    PlayerIdentificationConfig,
)
from src.types.errors import AnalysisError, ImageReadError, ConfigError
from src.types.player_identification import PlayerIdentity, PlayerDetectionResult

__all__ = [
    "PhotoMetadata",
    "PhotoScore",
    "AnalysisResult",
    "Config",
    "AnalysisConfig",
    "WeightsConfig",
    "ThresholdsConfig",
    "PlayerIdentificationConfig",
    "AnalysisError",
    "ImageReadError",
    "ConfigError",
    "PlayerIdentity",
    "PlayerDetectionResult",
]
