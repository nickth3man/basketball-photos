from __future__ import annotations

from src.types.config import TaggerThresholds
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


class Tagger:
    def __init__(self, thresholds: TaggerThresholds | None = None):
        self.thresholds = thresholds or TaggerThresholds()

    def build_tags(
        self,
        metadata: PhotoMetadata,
        scores: PhotoScore,
        category: str,
        *,
        context_text: str | None = None,
    ) -> list[str]:
        tags = {category, metadata.resolution_tier}

        if metadata.is_portrait:
            tags.add("portrait-orientation")
        elif metadata.is_square:
            tags.add("square-friendly")
        else:
            tags.add("landscape-orientation")

        if scores.action_moment >= self.thresholds.high_action:
            tags.add("high-action")
        elif scores.action_moment <= self.thresholds.low_action:
            tags.add("low-action")

        if scores.emotional_impact >= self.thresholds.high_emotional:
            tags.add("emotional")
        if scores.subject_isolation >= self.thresholds.high_subject:
            tags.add("subject-forward")
        if scores.instagram_suitability >= self.thresholds.instagram_ready:
            tags.add("instagram-ready")
        if (
            scores.color_quality <= self.thresholds.archival_color
            and scores.technical_quality <= self.thresholds.archival_tech
        ):
            tags.add("archival-look")
        if context_text and any(
            word in context_text.lower()
            for word in ["meme", "finals", "historic", "olympic"]
        ):
            tags.add("editorial-context")

        return sorted(tags)
