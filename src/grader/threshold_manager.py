from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.grader.comparator import BenchmarkProfile


class ThresholdManager:
    def determine_threshold(self, profile: "BenchmarkProfile", strategy: str) -> float:
        if strategy == "all":
            return profile.max_overall
        if strategy == "median":
            return profile.median_overall
        if strategy == "average":
            return profile.average_overall
        return max(profile.average_overall, profile.top_quartile_overall)
