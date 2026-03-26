import unittest

from src.categorizer.tagger import Tagger
from src.types.config import TaggerThresholds
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_metadata(*, width: int = 1200, height: int = 1600) -> PhotoMetadata:
    return PhotoMetadata(
        path="sample.jpg",
        filename="sample.jpg",
        width=width,
        height=height,
        format="JPEG",
        file_size=1000,
        color_mode="RGB",
    )


def build_scores(**overrides: float) -> PhotoScore:
    defaults = {
        "resolution_clarity": 6.0,
        "composition": 6.0,
        "action_moment": 6.0,
        "lighting": 6.0,
        "color_quality": 6.0,
        "subject_isolation": 6.0,
        "emotional_impact": 6.0,
        "technical_quality": 6.0,
        "relevance": 6.0,
        "instagram_suitability": 6.0,
    }
    defaults.update(overrides)
    return PhotoScore(**defaults, weights={})


class TestTagger(unittest.TestCase):
    def test_build_tags_is_sorted_and_combines_expected_labels(self) -> None:
        tagger = Tagger()
        tags = tagger.build_tags(
            build_metadata(width=1080, height=1080),
            build_scores(
                action_moment=8.0,
                emotional_impact=7.5,
                subject_isolation=7.5,
                instagram_suitability=7.5,
                color_quality=4.0,
                technical_quality=5.0,
            ),
            "celebration",
            context_text="historic finals meme",
        )

        self.assertEqual(tags, sorted(tags))
        self.assertIn("celebration", tags)
        self.assertIn("square-friendly", tags)
        self.assertIn("high-action", tags)
        self.assertIn("emotional", tags)
        self.assertIn("subject-forward", tags)
        self.assertIn("instagram-ready", tags)
        self.assertIn("archival-look", tags)
        self.assertIn("editorial-context", tags)

    def test_build_tags_uses_low_action_and_landscape_labels(self) -> None:
        tagger = Tagger()
        tags = tagger.build_tags(
            build_metadata(width=1800, height=900),
            build_scores(action_moment=4.5),
            "court_side",
        )

        self.assertIn("low-action", tags)
        self.assertIn("landscape-orientation", tags)

    def test_custom_thresholds_shift_tagging_behavior(self) -> None:
        tagger = Tagger(
            thresholds=TaggerThresholds(
                high_action=9.0,
                low_action=4.0,
                high_emotional=8.0,
                high_subject=8.0,
                instagram_ready=8.0,
                archival_color=3.0,
                archival_tech=4.0,
            )
        )

        tags = tagger.build_tags(
            build_metadata(),
            build_scores(action_moment=8.0, emotional_impact=7.5),
            "portrait",
        )

        self.assertNotIn("high-action", tags)
        self.assertNotIn("emotional", tags)
