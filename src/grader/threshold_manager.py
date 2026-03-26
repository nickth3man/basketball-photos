from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.grader.comparator import BenchmarkProfile


# TODO: Add a focused test module for each strategy branch and invalid input
# path before expanding this into a richer threshold selection policy.


class ThresholdManager:
    def determine_threshold(self, profile: "BenchmarkProfile", strategy: str) -> float:
        # TODO: Replace the free-form strategy string with an enum or literal
        # type so unsupported strategies fail earlier and more clearly.
        if strategy == "all":
            return profile.max_overall
        if strategy == "median":
            return profile.median_overall
        if strategy == "average":
            return profile.average_overall
        return max(profile.average_overall, profile.top_quartile_overall)
