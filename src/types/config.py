"""Configuration dataclasses matching settings.yaml structure."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ThresholdStrategy(str, Enum):
    """Valid threshold determination strategies."""

    ALL = "all"
    MEDIAN = "median"
    AVERAGE = "average"
    BLEND = "blend"

    @classmethod
    def from_string(cls, value: str) -> "ThresholdStrategy":
        try:
            return cls(value.lower())
        except ValueError:
            supported = ", ".join(strategy.value for strategy in cls)
            raise ValueError(
                f"Unsupported threshold strategy '{value}'. "
                f"Expected one of: {supported}"
            )


@dataclass
class AnalysisConfig:
    """Image analysis settings."""

    min_width: int = 1080
    min_height: int = 1080
    formats: list[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".webp"]
    )
    batch_size: int = 10
    max_image_pixels: int = 178_956_970
    max_image_mb: int = 100


@dataclass
class WeightsConfig:
    """Grading rubric weights. All weights should sum to approximately 1.0."""

    resolution_clarity: float = 0.12
    composition: float = 0.12
    action_moment: float = 0.15
    lighting: float = 0.10
    color_quality: float = 0.08
    subject_isolation: float = 0.10
    emotional_impact: float = 0.13
    technical_quality: float = 0.10
    relevance: float = 0.05
    instagram_suitability: float = 0.05

    def validate(self, tolerance: float = 0.01) -> bool:
        total = (
            self.resolution_clarity
            + self.composition
            + self.action_moment
            + self.lighting
            + self.color_quality
            + self.subject_isolation
            + self.emotional_impact
            + self.technical_quality
            + self.relevance
            + self.instagram_suitability
        )
        return abs(total - 1.0) <= tolerance

    def to_dict(self) -> dict[str, float]:
        return {
            "resolution_clarity": self.resolution_clarity,
            "composition": self.composition,
            "action_moment": self.action_moment,
            "lighting": self.lighting,
            "color_quality": self.color_quality,
            "subject_isolation": self.subject_isolation,
            "emotional_impact": self.emotional_impact,
            "technical_quality": self.technical_quality,
            "relevance": self.relevance,
            "instagram_suitability": self.instagram_suitability,
        }


@dataclass
class ThresholdsConfig:
    """Grade thresholds for categorization."""

    excellent: float = 9.0
    good: float = 7.5
    acceptable: float = 6.0
    poor: float = 4.0


@dataclass
class ClassifierThresholds:
    """Score thresholds for photo classification."""

    high_action: float = 7.5
    medium_action: float = 6.0
    high_emotional_impact: float = 7.0
    high_subject_isolation: float = 6.5


@dataclass
class TaggerThresholds:
    """Score thresholds for tag generation."""

    high_action: float = 7.5
    low_action: float = 5.0
    high_emotional: float = 7.0
    high_subject: float = 7.0
    instagram_ready: float = 7.0
    archival_color: float = 4.5
    archival_tech: float = 5.5


@dataclass
class DiscoveryConfig:
    """Settings for photo discovery (future use)."""

    min_overall_grade: float = 7.0
    target_count: int = 50
    download_dir: str = "./discovered"
    rate_limit: int = 2


@dataclass
class OutputConfig:
    """Output settings."""

    database: str = "./data/photo_grades.db"
    reports_dir: str = "./reports"
    export_format: str = "html"


@dataclass
class InstagramConfig:
    """Instagram optimization settings."""

    optimal_aspect_ratio: float = 1.0
    min_resolution: int = 1080
    max_file_size_mb: int = 8
    preferred_formats: list[str] = field(default_factory=lambda: ["jpg", "png"])


@dataclass
class Config:
    """Main configuration container."""

    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    weights: WeightsConfig = field(default_factory=WeightsConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    classifier_thresholds: ClassifierThresholds = field(
        default_factory=ClassifierThresholds
    )
    tagger_thresholds: TaggerThresholds = field(default_factory=TaggerThresholds)
    categories: list[str] = field(
        default_factory=lambda: [
            "action_shot",
            "portrait",
            "celebration",
            "dunk",
            "three_pointer",
            "defense",
            "team_photo",
            "court_side",
            "fan_moment",
            "iconic_moment",
        ]
    )
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    instagram: InstagramConfig = field(default_factory=InstagramConfig)

    def validate(self) -> list[str]:
        issues = []

        if not self.weights.validate():
            total = sum(self.weights.to_dict().values())
            issues.append(f"Weights sum to {total:.3f}, expected ~1.0")

        if self.analysis.min_width < 100:
            issues.append(f"min_width ({self.analysis.min_width}) seems too low")

        if self.analysis.min_height < 100:
            issues.append(f"min_height ({self.analysis.min_height}) seems too low")

        if self.thresholds.excellent <= self.thresholds.good:
            issues.append("excellent threshold should be higher than good")

        if self.thresholds.good <= self.thresholds.acceptable:
            issues.append("good threshold should be higher than acceptable")

        return issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": {
                "min_width": self.analysis.min_width,
                "min_height": self.analysis.min_height,
                "formats": self.analysis.formats,
                "batch_size": self.analysis.batch_size,
                "max_image_pixels": self.analysis.max_image_pixels,
                "max_image_mb": self.analysis.max_image_mb,
            },
            "weights": self.weights.to_dict(),
            "thresholds": {
                "excellent": self.thresholds.excellent,
                "good": self.thresholds.good,
                "acceptable": self.thresholds.acceptable,
                "poor": self.thresholds.poor,
            },
            "classifier_thresholds": {
                "high_action": self.classifier_thresholds.high_action,
                "medium_action": self.classifier_thresholds.medium_action,
                "high_emotional_impact": self.classifier_thresholds.high_emotional_impact,
                "high_subject_isolation": self.classifier_thresholds.high_subject_isolation,
            },
            "tagger_thresholds": {
                "high_action": self.tagger_thresholds.high_action,
                "low_action": self.tagger_thresholds.low_action,
                "high_emotional": self.tagger_thresholds.high_emotional,
                "high_subject": self.tagger_thresholds.high_subject,
                "instagram_ready": self.tagger_thresholds.instagram_ready,
                "archival_color": self.tagger_thresholds.archival_color,
                "archival_tech": self.tagger_thresholds.archival_tech,
            },
            "categories": self.categories,
            "discovery": {
                "min_overall_grade": self.discovery.min_overall_grade,
                "target_count": self.discovery.target_count,
                "download_dir": self.discovery.download_dir,
                "rate_limit": self.discovery.rate_limit,
            },
            "output": {
                "database": self.output.database,
                "reports_dir": self.output.reports_dir,
                "export_format": self.output.export_format,
            },
            "instagram": {
                "optimal_aspect_ratio": self.instagram.optimal_aspect_ratio,
                "min_resolution": self.instagram.min_resolution,
                "max_file_size_mb": self.instagram.max_file_size_mb,
                "preferred_formats": self.instagram.preferred_formats,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        analysis_data = data.get("analysis", {})
        weights_data = data.get("weights", {})
        thresholds_data = data.get("thresholds", {})
        classifier_thresholds_data = data.get("classifier_thresholds", {})
        tagger_thresholds_data = data.get("tagger_thresholds", {})
        categories_data = data.get("categories", [])
        discovery_data = data.get("discovery", {})
        output_data = data.get("output", {})
        instagram_data = data.get("instagram", {})

        return cls(
            analysis=AnalysisConfig(
                min_width=analysis_data.get("min_width", 1080),
                min_height=analysis_data.get("min_height", 1080),
                formats=analysis_data.get(
                    "formats", [".jpg", ".jpeg", ".png", ".webp"]
                ),
                batch_size=analysis_data.get("batch_size", 10),
                max_image_pixels=analysis_data.get("max_image_pixels", 178_956_970),
                max_image_mb=analysis_data.get("max_image_mb", 100),
            ),
            weights=WeightsConfig(
                resolution_clarity=weights_data.get("resolution_clarity", 0.12),
                composition=weights_data.get("composition", 0.12),
                action_moment=weights_data.get("action_moment", 0.15),
                lighting=weights_data.get("lighting", 0.10),
                color_quality=weights_data.get("color_quality", 0.08),
                subject_isolation=weights_data.get("subject_isolation", 0.10),
                emotional_impact=weights_data.get("emotional_impact", 0.13),
                technical_quality=weights_data.get("technical_quality", 0.10),
                relevance=weights_data.get("relevance", 0.05),
                instagram_suitability=weights_data.get("instagram_suitability", 0.05),
            ),
            thresholds=ThresholdsConfig(
                excellent=thresholds_data.get("excellent", 9.0),
                good=thresholds_data.get("good", 7.5),
                acceptable=thresholds_data.get("acceptable", 6.0),
                poor=thresholds_data.get("poor", 4.0),
            ),
            classifier_thresholds=ClassifierThresholds(
                high_action=classifier_thresholds_data.get("high_action", 7.5),
                medium_action=classifier_thresholds_data.get("medium_action", 6.0),
                high_emotional_impact=classifier_thresholds_data.get(
                    "high_emotional_impact", 7.0
                ),
                high_subject_isolation=classifier_thresholds_data.get(
                    "high_subject_isolation", 6.5
                ),
            ),
            tagger_thresholds=TaggerThresholds(
                high_action=tagger_thresholds_data.get("high_action", 7.5),
                low_action=tagger_thresholds_data.get("low_action", 5.0),
                high_emotional=tagger_thresholds_data.get("high_emotional", 7.0),
                high_subject=tagger_thresholds_data.get("high_subject", 7.0),
                instagram_ready=tagger_thresholds_data.get("instagram_ready", 7.0),
                archival_color=tagger_thresholds_data.get("archival_color", 4.5),
                archival_tech=tagger_thresholds_data.get("archival_tech", 5.5),
            ),
            categories=categories_data
            if categories_data
            else [
                "action_shot",
                "portrait",
                "celebration",
                "dunk",
                "three_pointer",
                "defense",
                "team_photo",
                "court_side",
                "fan_moment",
                "iconic_moment",
            ],
            discovery=DiscoveryConfig(
                min_overall_grade=discovery_data.get("min_overall_grade", 7.0),
                target_count=discovery_data.get("target_count", 50),
                download_dir=discovery_data.get("download_dir", "./discovered"),
                rate_limit=discovery_data.get("rate_limit", 2),
            ),
            output=OutputConfig(
                database=output_data.get("database", "./data/photo_grades.db"),
                reports_dir=output_data.get("reports_dir", "./reports"),
                export_format=output_data.get("export_format", "html"),
            ),
            instagram=InstagramConfig(
                optimal_aspect_ratio=instagram_data.get("optimal_aspect_ratio", 1.0),
                min_resolution=instagram_data.get("min_resolution", 1080),
                max_file_size_mb=instagram_data.get("max_file_size_mb", 8),
                preferred_formats=instagram_data.get(
                    "preferred_formats", ["jpg", "png"]
                ),
            ),
        )
