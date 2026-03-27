"""Analysis result dataclass combining metadata, scores, and categorization."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.types.player_identification import PlayerIdentity


@dataclass
class AnalysisResult:
    """Complete analysis result for a single photo.

    Combines metadata, scores, categorization, and tags into a single result.

    Attributes:
        metadata: PhotoMetadata for the analyzed image
        scores: PhotoScore with 10-parameter rubric results
        category: Primary category classification
        tags: List of secondary tags
        analyzed_at: Timestamp when analysis was performed
        analyzer_version: Version of the analyzer used
        errors: List of any errors encountered during analysis
        player_identities: List of identified players in the photo
        needs_identity_review: Whether player identities need manual review
    """

    metadata: Any  # PhotoMetadata (using Any to avoid circular import)
    scores: Any  # PhotoScore
    category: str
    tags: list[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)
    analyzer_version: str = "0.1.0"
    errors: list[str] = field(default_factory=list)
    player_identities: list["PlayerIdentity"] = field(default_factory=list)
    needs_identity_review: bool = False

    @property
    def is_high_quality(self) -> bool:
        """Check if photo meets high quality threshold (>=7.0)."""
        return self.scores.overall_score >= 7.0

    @property
    def is_instagram_ready(self) -> bool:
        """Check if photo is suitable for Instagram (>=6.0 and square-ish)."""
        return (
            self.scores.overall_score >= 6.0
            and self.scores.instagram_suitability >= 5.0
        )

    @property
    def needs_review(self) -> bool:
        """Check if photo needs manual review (score 5-7)."""
        return 5.0 <= self.scores.overall_score < 7.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "scores": self.scores.to_dict(),
            "category": self.category,
            "tags": self.tags,
            "analyzed_at": self.analyzed_at.isoformat(),
            "analyzer_version": self.analyzer_version,
            "errors": self.errors,
            "is_high_quality": self.is_high_quality,
            "is_instagram_ready": self.is_instagram_ready,
            "needs_review": self.needs_review,
            "player_identities": [p.to_dict() for p in self.player_identities],
            "needs_identity_review": self.needs_identity_review,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisResult":
        """Create AnalysisResult from dictionary."""
        from src.types.photo import PhotoMetadata
        from src.types.player_identification import PlayerIdentity
        from src.types.scores import PhotoScore

        metadata = PhotoMetadata.from_dict(data["metadata"])
        scores = PhotoScore.from_dict(data["scores"])

        player_identities = []
        if "player_identities" in data:
            player_identities = [
                PlayerIdentity.from_dict(p) for p in data["player_identities"]
            ]

        return cls(
            metadata=metadata,
            scores=scores,
            category=data["category"],
            tags=data.get("tags", []),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"])
            if "analyzed_at" in data
            else datetime.now(),
            analyzer_version=data.get("analyzer_version", "0.1.0"),
            errors=data.get("errors", []),
            player_identities=player_identities,
            needs_identity_review=data.get("needs_identity_review", False),
        )
