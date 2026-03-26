import unittest

from src.grader.comparator import BenchmarkProfile
from src.grader.threshold_manager import ThresholdManager
from src.types.config import ThresholdStrategy


class TestThresholdManager(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ThresholdManager()
        self.profile = BenchmarkProfile(
            average_overall=6.8,
            median_overall=6.6,
            max_overall=8.1,
            min_overall=5.3,
            top_quartile_overall=7.4,
            category_distribution={"portrait": 2},
            top_tags=["portrait-orientation"],
        )

    def test_accepts_enum_strategy_values(self) -> None:
        self.assertEqual(
            self.manager.determine_threshold(self.profile, ThresholdStrategy.ALL),
            8.1,
        )
        self.assertEqual(
            self.manager.determine_threshold(self.profile, ThresholdStrategy.AVERAGE),
            6.8,
        )
        self.assertEqual(
            self.manager.determine_threshold(self.profile, ThresholdStrategy.MEDIAN),
            6.6,
        )
        self.assertEqual(
            self.manager.determine_threshold(self.profile, ThresholdStrategy.BLEND),
            7.4,
        )

    def test_accepts_string_strategy_values(self) -> None:
        self.assertEqual(self.manager.determine_threshold(self.profile, "all"), 8.1)
        self.assertEqual(self.manager.determine_threshold(self.profile, "average"), 6.8)
        self.assertEqual(self.manager.determine_threshold(self.profile, "median"), 6.6)
        self.assertEqual(self.manager.determine_threshold(self.profile, "blend"), 7.4)

    def test_rejects_invalid_strategy(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.determine_threshold(self.profile, "unknown")
