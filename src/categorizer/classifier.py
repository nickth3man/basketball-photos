from __future__ import annotations

from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


# TODO: Add tests that cover every classification branch, especially the
# context-text shortcuts and configured-category fallbacks.


class Classifier:
    def __init__(self, configured_categories: list[str]):
        self.configured_categories = configured_categories

    def classify(
        self,
        metadata: PhotoMetadata,
        scores: PhotoScore,
        *,
        context_text: str | None = None,
    ) -> str:
        # TODO: Move the score thresholds into configuration once the current
        # heuristic breakpoints have dedicated regression coverage.
        normalized = (context_text or "").lower()

        if any(keyword in normalized for keyword in ["group photo", "team", "squad"]):
            return self._configured_or_default("team_photo", "court_side")
        if any(keyword in normalized for keyword in ["portrait", "headshot"]):
            return self._configured_or_default("portrait", "iconic_moment")
        if any(keyword in normalized for keyword in ["historic", "vintage", "iconic"]):
            return self._configured_or_default("iconic_moment", "portrait")
        if any(
            keyword in normalized for keyword in ["celebration", "champion", "finals"]
        ):
            return self._configured_or_default("celebration", "iconic_moment")

        if scores.action_moment >= 8.0 and scores.emotional_impact >= 7.5:
            return self._configured_or_default("celebration", "action_shot")

        if scores.action_moment >= 7.5:
            if metadata.is_portrait:
                return self._configured_or_default("dunk", "action_shot")
            return self._configured_or_default("action_shot", "iconic_moment")

        if scores.subject_isolation >= 6.5 and metadata.is_portrait:
            return self._configured_or_default("portrait", "iconic_moment")

        if scores.emotional_impact >= 7.0 and scores.action_moment < 6.0:
            return self._configured_or_default("iconic_moment", "portrait")

        if metadata.is_landscape and scores.subject_isolation < 5.0:
            return self._configured_or_default("team_photo", "court_side")

        return self._configured_or_default("court_side", "action_shot")

    def _configured_or_default(self, preferred: str, fallback: str) -> str:
        if preferred in self.configured_categories:
            return preferred
        if fallback in self.configured_categories:
            return fallback
        return (
            self.configured_categories[0] if self.configured_categories else preferred
        )
