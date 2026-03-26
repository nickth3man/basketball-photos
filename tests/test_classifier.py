import unittest

from src.categorizer.classifier import Classifier
from src.types.config import ClassifierThresholds
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


class TestClassifier(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = Classifier(
            [
                "action_shot",
                "portrait",
                "celebration",
                "team_photo",
                "court_side",
                "iconic_moment",
                "dunk",
            ]
        )

    def test_context_shortcuts_choose_expected_category(self) -> None:
        metadata = build_metadata()
        scores = build_scores()

        self.assertEqual(
            self.classifier.classify(metadata, scores, context_text="team squad photo"),
            "team_photo",
        )
        self.assertEqual(
            self.classifier.classify(metadata, scores, context_text="historic icon"),
            "iconic_moment",
        )
        self.assertEqual(
            self.classifier.classify(
                metadata, scores, context_text="portrait headshot"
            ),
            "portrait",
        )
        self.assertEqual(
            self.classifier.classify(
                metadata, scores, context_text="finals celebration"
            ),
            "celebration",
        )

    def test_score_based_branches_cover_major_outcomes(self) -> None:
        portrait_metadata = build_metadata(width=1000, height=1500)
        landscape_metadata = build_metadata(width=1800, height=900)

        self.assertEqual(
            self.classifier.classify(
                portrait_metadata,
                build_scores(action_moment=8.0, emotional_impact=8.0),
            ),
            "celebration",
        )
        self.assertEqual(
            self.classifier.classify(
                portrait_metadata,
                build_scores(action_moment=8.0, emotional_impact=6.0),
            ),
            "dunk",
        )
        self.assertEqual(
            self.classifier.classify(
                portrait_metadata,
                build_scores(subject_isolation=7.0),
            ),
            "portrait",
        )
        self.assertEqual(
            self.classifier.classify(
                landscape_metadata,
                build_scores(subject_isolation=4.0),
            ),
            "team_photo",
        )
        self.assertEqual(
            self.classifier.classify(
                portrait_metadata,
                build_scores(emotional_impact=7.2, action_moment=5.5),
            ),
            "iconic_moment",
        )

    def test_fallback_uses_configured_categories(self) -> None:
        classifier = Classifier(["court_side"])
        metadata = build_metadata(width=1800, height=900)
        scores = build_scores(subject_isolation=4.0)

        self.assertEqual(classifier.classify(metadata, scores), "court_side")

    def test_custom_thresholds_shift_behavior(self) -> None:
        classifier = Classifier(
            ["action_shot", "celebration", "portrait", "iconic_moment"],
            thresholds=ClassifierThresholds(
                high_action=9.0,
                medium_action=7.0,
                high_emotional_impact=8.5,
                high_subject_isolation=7.5,
            ),
        )

        result = classifier.classify(
            build_metadata(),
            build_scores(
                action_moment=8.0, emotional_impact=8.0, subject_isolation=7.6
            ),
        )

        self.assertEqual(result, "portrait")
