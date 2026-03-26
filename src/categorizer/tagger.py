from __future__ import annotations

from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


# TODO: Add dedicated tests for tag combinations and ordering so future tag
# additions do not silently change discovery query inputs.


class Tagger:
    def build_tags(
        self,
        metadata: PhotoMetadata,
        scores: PhotoScore,
        category: str,
        *,
        context_text: str | None = None,
    ) -> list[str]:
        # TODO: Promote the hard-coded score thresholds here into config once
        # product-facing tag names and cutoffs are stable.
        tags = {category, metadata.resolution_tier}

        if metadata.is_portrait:
            tags.add("portrait-orientation")
        elif metadata.is_square:
            tags.add("square-friendly")
        else:
            tags.add("landscape-orientation")

        if scores.action_moment >= 7.5:
            tags.add("high-action")
        elif scores.action_moment <= 5.0:
            tags.add("low-action")

        if scores.emotional_impact >= 7.0:
            tags.add("emotional")
        if scores.subject_isolation >= 7.0:
            tags.add("subject-forward")
        if scores.instagram_suitability >= 7.0:
            tags.add("instagram-ready")
        if scores.color_quality <= 4.5 and scores.technical_quality <= 5.5:
            tags.add("archival-look")
        if context_text and any(
            word in context_text.lower()
            for word in ["meme", "finals", "historic", "olympic"]
        ):
            tags.add("editorial-context")

        return sorted(tags)
