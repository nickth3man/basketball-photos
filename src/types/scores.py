"""Photo scoring dataclass for the 10-parameter rubric."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PhotoScore:
    """Scores for a photo based on the 10-parameter rubric.

    All individual scores are on a 1-10 scale.
    The overall_score is a weighted average based on config weights.

    Attributes:
        resolution_clarity: Image sharpness, pixel density, absence of blur
        composition: Rule of thirds, framing, visual balance
        action_moment: Peak action capture, decisive moments
        lighting: Exposure, contrast, dynamic range
        color_quality: Saturation, color accuracy, vibrancy
        subject_isolation: Player prominence, background separation
        emotional_impact: Drama, intensity, storytelling
        technical_quality: Noise, artifacts, compression quality
        relevance: Current players, trending teams, iconic moments
        instagram_suitability: Square format friendly, mobile viewport optimized
        overall_score: Weighted average of all parameters
        weights: Dictionary of weights used for calculation
    """

    resolution_clarity: float
    composition: float
    action_moment: float
    lighting: float
    color_quality: float
    subject_isolation: float
    emotional_impact: float
    technical_quality: float
    relevance: float
    instagram_suitability: float
    overall_score: float = field(init=False)
    weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate overall score after initialization."""
        self._validate_scores()
        self.overall_score = self._calculate_overall()

    def _validate_scores(self) -> None:
        """Ensure all scores are within valid range (1-10)."""
        score_fields = [
            self.resolution_clarity,
            self.composition,
            self.action_moment,
            self.lighting,
            self.color_quality,
            self.subject_isolation,
            self.emotional_impact,
            self.technical_quality,
            self.relevance,
            self.instagram_suitability,
        ]
        for score in score_fields:
            if not 1.0 <= score <= 10.0:
                raise ValueError(f"Score must be between 1.0 and 10.0, got {score}")

    def _calculate_overall(self) -> float:
        """Calculate weighted overall score."""
        if not self.weights:
            # Default equal weights if not provided
            return (
                sum(
                    [
                        self.resolution_clarity,
                        self.composition,
                        self.action_moment,
                        self.lighting,
                        self.color_quality,
                        self.subject_isolation,
                        self.emotional_impact,
                        self.technical_quality,
                        self.relevance,
                        self.instagram_suitability,
                    ]
                )
                / 10.0
            )

        weighted_sum = (
            self.resolution_clarity * self.weights.get("resolution_clarity", 0.1)
            + self.composition * self.weights.get("composition", 0.1)
            + self.action_moment * self.weights.get("action_moment", 0.1)
            + self.lighting * self.weights.get("lighting", 0.1)
            + self.color_quality * self.weights.get("color_quality", 0.1)
            + self.subject_isolation * self.weights.get("subject_isolation", 0.1)
            + self.emotional_impact * self.weights.get("emotional_impact", 0.1)
            + self.technical_quality * self.weights.get("technical_quality", 0.1)
            + self.relevance * self.weights.get("relevance", 0.1)
            + self.instagram_suitability
            * self.weights.get("instagram_suitability", 0.1)
        )
        return round(weighted_sum, 2)

    @property
    def grade(self) -> str:
        """Return letter grade based on overall score."""
        if self.overall_score >= 9.0:
            return "A+"
        elif self.overall_score >= 8.5:
            return "A"
        elif self.overall_score >= 8.0:
            return "A-"
        elif self.overall_score >= 7.5:
            return "B+"
        elif self.overall_score >= 7.0:
            return "B"
        elif self.overall_score >= 6.5:
            return "B-"
        elif self.overall_score >= 6.0:
            return "C+"
        elif self.overall_score >= 5.5:
            return "C"
        elif self.overall_score >= 5.0:
            return "C-"
        elif self.overall_score >= 4.0:
            return "D"
        else:
            return "F"

    @property
    def quality_tier(self) -> str:
        """Return quality tier based on thresholds."""
        if self.overall_score >= 9.0:
            return "excellent"
        elif self.overall_score >= 7.5:
            return "good"
        elif self.overall_score >= 6.0:
            return "acceptable"
        elif self.overall_score >= 4.0:
            return "poor"
        else:
            return "unacceptable"

    @property
    def top_three_params(self) -> list[tuple[str, float]]:
        """Return the three highest-scoring parameters."""
        params = [
            ("resolution_clarity", self.resolution_clarity),
            ("composition", self.composition),
            ("action_moment", self.action_moment),
            ("lighting", self.lighting),
            ("color_quality", self.color_quality),
            ("subject_isolation", self.subject_isolation),
            ("emotional_impact", self.emotional_impact),
            ("technical_quality", self.technical_quality),
            ("relevance", self.relevance),
            ("instagram_suitability", self.instagram_suitability),
        ]
        return sorted(params, key=lambda x: x[1], reverse=True)[:3]

    @property
    def bottom_three_params(self) -> list[tuple[str, float]]:
        """Return the three lowest-scoring parameters."""
        params = [
            ("resolution_clarity", self.resolution_clarity),
            ("composition", self.composition),
            ("action_moment", self.action_moment),
            ("lighting", self.lighting),
            ("color_quality", self.color_quality),
            ("subject_isolation", self.subject_isolation),
            ("emotional_impact", self.emotional_impact),
            ("technical_quality", self.technical_quality),
            ("relevance", self.relevance),
            ("instagram_suitability", self.instagram_suitability),
        ]
        return sorted(params, key=lambda x: x[1])[:3]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
            "overall_score": self.overall_score,
            "grade": self.grade,
            "quality_tier": self.quality_tier,
            "weights": self.weights,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhotoScore":
        """Create PhotoScore from dictionary."""
        weights = data.pop("weights", {})
        # Remove calculated fields if present
        data.pop("overall_score", None)
        data.pop("grade", None)
        data.pop("quality_tier", None)
        return cls(weights=weights, **data)
