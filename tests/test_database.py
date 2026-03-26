import unittest

from src.storage import PhotoDatabase
from src.types.analysis import AnalysisResult
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_result(path: str, category: str = "action_shot") -> AnalysisResult:
    metadata = PhotoMetadata(
        path=path,
        filename=path,
        width=1920,
        height=1080,
        format="JPEG",
        file_size=300000,
        color_mode="RGB",
    )
    scores = PhotoScore(
        resolution_clarity=6.0,
        composition=6.0,
        action_moment=6.0,
        lighting=6.0,
        color_quality=6.0,
        subject_isolation=6.0,
        emotional_impact=6.0,
        technical_quality=6.0,
        relevance=6.0,
        instagram_suitability=6.0,
        weights={},
    )
    return AnalysisResult(
        metadata=metadata,
        scores=scores,
        category=category,
        tags=["sample", category],
    )


class TestDatabase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = PhotoDatabase(":memory:")

    def tearDown(self) -> None:
        self.db.close()

    def test_save_and_retrieve_analysis(self) -> None:
        result = build_result("test.jpg")
        photo_id = self.db.save_analysis(result)

        self.assertGreater(photo_id, 0)

        retrieved = self.db.get_photo_by_path("test.jpg")
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved["filename"], "test.jpg")
        self.assertEqual(retrieved["scores"]["overall_score"], 6.0)
        self.assertEqual(retrieved["categories"]["primary_category"], "action_shot")

    def test_statistics_reflect_saved_rows(self) -> None:
        self.db.save_analysis(build_result("one.jpg", category="portrait"))
        self.db.save_analysis(build_result("two.jpg", category="portrait"))

        stats = self.db.get_statistics()

        self.assertEqual(stats["total_photos"], 2)
        self.assertEqual(stats["average_score"], 6.0)
        self.assertEqual(stats["category_distribution"], {"portrait": 2})

    def test_get_top_photos_returns_saved_items(self) -> None:
        # TODO: Expand this suite to cover get_all_photos(),
        # get_photos_by_category(), delete_photo(), and clear_all().
        self.db.save_analysis(build_result("top.jpg", category="iconic_moment"))
        results = self.db.get_top_photos(limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "top.jpg")


if __name__ == "__main__":
    unittest.main()
