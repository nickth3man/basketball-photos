from __future__ import annotations

import unittest
from datetime import datetime

from src.grader.comparator import Comparator
from src.grader.threshold_manager import ThresholdManager
from src.types.analysis import AnalysisResult
from src.types.config import ThresholdStrategy
from src.types.errors import ValidationError
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
    def setUp(self) -> None:
        self.comparator = Comparator()
        self.threshold_manager = ThresholdManager()
        self.base = {
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

    def test_profile_and_compare(self) -> None:
        strong = self.base | {"action_moment": 8.0, "emotional_impact": 8.0}
        profile = self.comparator.build_profile(
            [
                build_result(
                    "one.jpg", self.base, "portrait", ["portrait-orientation"]
                ),
                build_result("two.jpg", strong, "action_shot", ["high-action"]),
            ]
        )

        candidate = build_result(
            "candidate.jpg", strong, "action_shot", ["high-action"]
        )
        comparison = self.comparator.compare(
            candidate, profile, strategy="average", threshold=profile.average_overall
        )

        self.assertTrue(comparison["accepted"])
        self.assertTrue(comparison["category_match"])

    def test_build_profile_rejects_empty_results(self) -> None:
        with self.assertRaises(ValidationError):
            self.comparator.build_profile([])

    def test_threshold_manager_supports_each_strategy(self) -> None:
        results = [
            build_result("one.jpg", self.base, "portrait", ["portrait-orientation"]),
            build_result(
                "two.jpg",
                self.base | {"action_moment": 8.0, "emotional_impact": 8.0},
                "action_shot",
                ["high-action"],
            ),
            build_result(
                "three.jpg",
                self.base | {"composition": 8.5},
                "court_side",
                ["editorial-context"],
            ),
        ]
        profile = self.comparator.build_profile(results)

        self.assertEqual(
            self.threshold_manager.determine_threshold(profile, ThresholdStrategy.ALL),
            profile.max_overall,
        )
        self.assertEqual(
            self.threshold_manager.determine_threshold(
                profile, ThresholdStrategy.MEDIAN
            ),
            profile.median_overall,
        )
        self.assertEqual(
            self.threshold_manager.determine_threshold(
                profile, ThresholdStrategy.AVERAGE
            ),
            profile.average_overall,
        )
        self.assertEqual(
            self.threshold_manager.determine_threshold(
                profile, ThresholdStrategy.BLEND
            ),
            max(profile.average_overall, profile.top_quartile_overall),
        )

    def test_threshold_manager_rejects_invalid_strategy(self) -> None:
        profile = self.comparator.build_profile(
            [build_result("one.jpg", self.base, "portrait", ["portrait-orientation"])]
        )

        with self.assertRaises(ValueError):
            self.threshold_manager.determine_threshold(profile, "not-a-strategy")


if __name__ == "__main__":
    unittest.main()
