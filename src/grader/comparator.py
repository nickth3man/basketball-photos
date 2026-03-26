from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median

from src.types.analysis import AnalysisResult


@dataclass
class BenchmarkProfile:
    average_overall: float
    median_overall: float
    max_overall: float
    min_overall: float
    top_quartile_overall: float
    category_distribution: dict[str, int]
    top_tags: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "average_overall": self.average_overall,
            "median_overall": self.median_overall,
            "max_overall": self.max_overall,
            "min_overall": self.min_overall,
            "top_quartile_overall": self.top_quartile_overall,
            "category_distribution": self.category_distribution,
            "top_tags": self.top_tags,
        }


class Comparator:
    def build_profile(self, results: list[AnalysisResult]) -> BenchmarkProfile:
        # TODO: Guard against empty result sets here so callers get a domain-
        # specific error instead of a generic statistics failure.
        ordered_scores = sorted(result.scores.overall_score for result in results)
        top_index = max(0, int(len(ordered_scores) * 0.75) - 1)

        category_distribution = Counter(result.category for result in results)
        tag_distribution = Counter(tag for result in results for tag in result.tags)

        return BenchmarkProfile(
            average_overall=round(sum(ordered_scores) / len(ordered_scores), 2),
            median_overall=round(float(median(ordered_scores)), 2),
            max_overall=round(max(ordered_scores), 2),
            min_overall=round(min(ordered_scores), 2),
            top_quartile_overall=round(ordered_scores[top_index], 2),
            category_distribution=dict(category_distribution),
            top_tags=[tag for tag, _ in tag_distribution.most_common(8)],
        )

    def compare(
        self,
        candidate: AnalysisResult,
        profile: BenchmarkProfile,
        *,
        strategy: str,
        threshold: float,
    ) -> dict[str, object]:
        # TODO: Add branch coverage for all threshold strategies and a few
        # boundary-score cases so acceptance logic stays trustworthy.
        category_match = candidate.category in profile.category_distribution
        tag_overlap = sorted(set(candidate.tags) & set(profile.top_tags))
        gap = round(candidate.scores.overall_score - threshold, 2)

        return {
            "accepted": candidate.scores.overall_score >= threshold,
            "strategy": strategy,
            "threshold": threshold,
            "overall_score": candidate.scores.overall_score,
            "gap": gap,
            "category_match": category_match,
            "tag_overlap": tag_overlap,
        }
