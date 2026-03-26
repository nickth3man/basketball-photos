from __future__ import annotations

import unittest
from datetime import datetime

from src.grader.comparator import Comparator
from src.types.analysis import AnalysisResult
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_result(
    name: str, overall_inputs: dict[str, float], category: str, tags: list[str]
) -> AnalysisResult:
    metadata = PhotoMetadata(
        path=name,
        filename=name,
        width=1400,
        height=1400,
        format="JPEG",
        file_size=1000,
        color_mode="RGB",
    )
    score = PhotoScore(weights={key: 0.1 for key in overall_inputs}, **overall_inputs)
    return AnalysisResult(
        metadata=metadata,
        scores=score,
        category=category,
        tags=tags,
        analyzed_at=datetime.now(),
    )


class ComparatorTest(unittest.TestCase):
    def test_profile_and_compare(self) -> None:
        # TODO: Add explicit tests for empty profiles and each threshold
        # strategy boundary instead of validating only the happy path.
        comparator = Comparator()
        base = {
            "resolution_clarity": 7.0,
            "composition": 7.0,
            "action_moment": 7.0,
            "lighting": 7.0,
            "color_quality": 7.0,
            "subject_isolation": 7.0,
            "emotional_impact": 7.0,
            "technical_quality": 7.0,
            "relevance": 7.0,
            "instagram_suitability": 7.0,
        }
        strong = base | {"action_moment": 8.0, "emotional_impact": 8.0}
        profile = comparator.build_profile(
            [
                build_result("one.jpg", base, "portrait", ["portrait-orientation"]),
                build_result("two.jpg", strong, "action_shot", ["high-action"]),
            ]
        )

        candidate = build_result(
            "candidate.jpg", strong, "action_shot", ["high-action"]
        )
        comparison = comparator.compare(
            candidate, profile, strategy="average", threshold=profile.average_overall
        )

        self.assertTrue(comparison["accepted"])
        self.assertTrue(comparison["category_match"])


if __name__ == "__main__":
    unittest.main()
