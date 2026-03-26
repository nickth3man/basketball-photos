"""Core types and dataclasses for photo analysis."""

from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore
from src.types.analysis import AnalysisResult
from src.types.config import Config, AnalysisConfig, WeightsConfig, ThresholdsConfig
from src.types.errors import AnalysisError, ImageReadError, ConfigError

__all__ = [
    "PhotoMetadata",
    "PhotoScore",
    "AnalysisResult",
    "Config",
    "AnalysisConfig",
    "WeightsConfig",
    "ThresholdsConfig",
    "AnalysisError",
    "ImageReadError",
    "ConfigError",
]
