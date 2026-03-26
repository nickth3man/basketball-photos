from __future__ import annotations

from typing import TYPE_CHECKING

from src.types.config import ThresholdStrategy

if TYPE_CHECKING:
    from src.grader.comparator import BenchmarkProfile


class ThresholdManager:
    def determine_threshold(
        self, profile: "BenchmarkProfile", strategy: str | ThresholdStrategy
    ) -> float:
        if isinstance(strategy, str):
            strategy = ThresholdStrategy.from_string(strategy)

        if strategy == ThresholdStrategy.ALL:
            return profile.max_overall
        if strategy == ThresholdStrategy.MEDIAN:
            return profile.median_overall
        if strategy == ThresholdStrategy.AVERAGE:
            return profile.average_overall
        return max(profile.average_overall, profile.top_quartile_overall)
