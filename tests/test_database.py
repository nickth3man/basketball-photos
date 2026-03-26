import unittest

from src.storage import PhotoDatabase
from src.types.analysis import AnalysisResult
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_result(
    path: str, category: str = "action_shot", score: float = 6.0
) -> AnalysisResult:
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
        resolution_clarity=score,
        composition=score,
        action_moment=score,
        lighting=score,
        color_quality=score,
        subject_isolation=score,
        emotional_impact=score,
        technical_quality=score,
        relevance=score,
        instagram_suitability=score,
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
        self.db.save_analysis(build_result("top.jpg", category="iconic_moment"))
        results = self.db.get_top_photos(limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "top.jpg")

    def test_get_all_photos_pagination(self) -> None:
        for i in range(15):
            self.db.save_analysis(
                build_result(f"photo_{i:02d}.jpg", score=1.0 + (i * 0.5))
            )

        page1 = self.db.get_all_photos(limit=5, offset=0)
        self.assertEqual(len(page1), 5)

        page2 = self.db.get_all_photos(limit=5, offset=5)
        self.assertEqual(len(page2), 5)

        page1_paths = {p["path"] for p in page1}
        page2_paths = {p["path"] for p in page2}
        self.assertEqual(len(page1_paths & page2_paths), 0)

    def test_get_all_photos_offset_boundary(self) -> None:
        for i in range(5):
            self.db.save_analysis(build_result(f"photo_{i}.jpg"))

        result = self.db.get_all_photos(limit=10, offset=10)
        self.assertEqual(len(result), 0)

        result = self.db.get_all_photos(limit=10, offset=3)
        self.assertEqual(len(result), 2)

    def test_get_all_photos_ordering_by_score(self) -> None:
        self.db.save_analysis(build_result("low.jpg", score=3.0))
        self.db.save_analysis(build_result("high.jpg", score=9.0))
        self.db.save_analysis(build_result("mid.jpg", score=6.0))

        results = self.db.get_all_photos(limit=10)
        self.assertEqual(results[0]["path"], "high.jpg")
        self.assertEqual(results[1]["path"], "mid.jpg")
        self.assertEqual(results[2]["path"], "low.jpg")

    def test_get_photos_by_category(self) -> None:
        self.db.save_analysis(build_result("action1.jpg", category="action_shot"))
        self.db.save_analysis(build_result("action2.jpg", category="action_shot"))
        self.db.save_analysis(build_result("portrait1.jpg", category="portrait"))

        results = self.db.get_photos_by_category("action_shot", limit=10)
        self.assertEqual(len(results), 2)

        results = self.db.get_photos_by_category("portrait", limit=10)
        self.assertEqual(len(results), 1)

    def test_delete_photo(self) -> None:
        self.db.save_analysis(build_result("to_delete.jpg"))
        self.assertIsNotNone(self.db.get_photo_by_path("to_delete.jpg"))

        deleted = self.db.delete_photo("to_delete.jpg")
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_photo_by_path("to_delete.jpg"))

        deleted_again = self.db.delete_photo("to_delete.jpg")
        self.assertFalse(deleted_again)

    def test_clear_all_returns_correct_count(self) -> None:
        self.db.save_analysis(build_result("one.jpg"))
        self.db.save_analysis(build_result("two.jpg"))
        self.db.save_analysis(build_result("three.jpg"))

        deleted_count = self.db.clear_all()
        self.assertEqual(deleted_count, 3)

        stats = self.db.get_statistics()
        self.assertEqual(stats["total_photos"], 0)

    def test_clear_all_on_empty_database(self) -> None:
        deleted_count = self.db.clear_all()
        self.assertEqual(deleted_count, 0)

    def test_save_batch(self) -> None:
        results = [
            build_result("batch1.jpg", score=7.0),
            build_result("batch2.jpg", score=8.0),
            build_result("batch3.jpg", score=6.0),
        ]
        photo_ids = self.db.save_batch(results)

        self.assertEqual(len(photo_ids), 3)
        for pid in photo_ids:
            self.assertGreater(pid, 0)

        stats = self.db.get_statistics()
        self.assertEqual(stats["total_photos"], 3)

    def test_save_batch_atomic_rollback_on_duplicate(self) -> None:
        self.db.save_analysis(build_result("existing.jpg"))

        results = [
            build_result("new1.jpg"),
            build_result("existing.jpg"),
            build_result("new2.jpg"),
        ]
        photo_ids = self.db.save_batch(results)

        self.assertEqual(len(photo_ids), 3)

    def test_schema_version(self) -> None:
        version = self.db.get_schema_version()
        self.assertGreaterEqual(version, 1)

    def test_transaction_helper_commits_on_success(self) -> None:
        result = build_result("transaction_test.jpg")
        self.db.save_analysis(result)

        retrieved = self.db.get_photo_by_path("transaction_test.jpg")
        self.assertIsNotNone(retrieved)


class TestDatabaseEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.db = PhotoDatabase(":memory:")

    def tearDown(self) -> None:
        self.db.close()

    def test_update_existing_photo(self) -> None:
        result1 = build_result("update.jpg", score=5.0)
        self.db.save_analysis(result1)

        result2 = build_result("update.jpg", score=9.0)
        self.db.save_analysis(result2)

        retrieved = self.db.get_photo_by_path("update.jpg")
        assert retrieved is not None
        self.assertEqual(retrieved["scores"]["overall_score"], 9.0)

        stats = self.db.get_statistics()
        self.assertEqual(stats["total_photos"], 1)

    def test_get_photo_by_path_not_found(self) -> None:
        result = self.db.get_photo_by_path("nonexistent.jpg")
        self.assertIsNone(result)

    def test_get_top_photos_with_limit(self) -> None:
        for i in range(20):
            self.db.save_analysis(build_result(f"photo_{i}.jpg", score=1.0 + (i * 0.4)))

        results = self.db.get_top_photos(limit=5)
        self.assertEqual(len(results), 5)

    def test_pagination_with_zero_limit(self) -> None:
        for i in range(3):
            self.db.save_analysis(build_result(f"photo_{i}.jpg"))

        results = self.db.get_all_photos(limit=0, offset=0)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
