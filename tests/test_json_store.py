"""Tests for JSON store functionality."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.storage.json_store import JSONStore
from src.types.analysis import AnalysisResult
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_result(path: str, score: float = 6.0) -> AnalysisResult:
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
        category="action_shot",
        tags=["sample"],
    )


class TestJSONStore(unittest.TestCase):
    """Test JSONStore functionality."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.store = JSONStore(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_single(self) -> None:
        result = build_result("test.jpg")
        self.store.export_single(result)

        output_file = Path(self.temp_dir) / "test.json"
        self.assertTrue(output_file.exists())

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["metadata"]["filename"], "test.jpg")

    def test_export_batch(self) -> None:
        results = [
            build_result("one.jpg", score=7.0),
            build_result("two.jpg", score=8.0),
            build_result("three.jpg", score=6.0),
        ]
        self.store.export_batch(results, filename="batch.json")

        output_file = Path(self.temp_dir) / "batch.json"
        self.assertTrue(output_file.exists())

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["total_photos"], 3)
        self.assertEqual(len(data["results"]), 3)
        self.assertIn("exported_at", data)

    def test_export_batch_creates_directory(self) -> None:
        nested_dir = os.path.join(self.temp_dir, "nested", "path")
        store = JSONStore(nested_dir)
        results = [build_result("test.jpg")]
        store.export_batch(results)

        output_file = Path(nested_dir) / "analysis_results.json"
        self.assertTrue(output_file.exists())

    def test_load_batch(self) -> None:
        results = [
            build_result("one.jpg", score=7.0),
            build_result("two.jpg", score=8.0),
        ]
        self.store.export_batch(results, filename="load_test.json")

        loaded = self.store.load_batch(filename="load_test.json")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(len(loaded), 2)

    def test_load_batch_missing_file(self) -> None:
        loaded = self.store.load_batch(filename="nonexistent.json")
        self.assertEqual(loaded, [])

    def test_load_batch_invalid_json_returns_empty_list(self) -> None:
        invalid_file = Path(self.temp_dir) / "invalid.json"
        invalid_file.write_text("{not valid json", encoding="utf-8")

        loaded = self.store.load_batch(filename="invalid.json")

        self.assertEqual(loaded, [])

    def test_export_dict(self) -> None:
        data = {
            "summary": {"total": 10, "average": 6.5},
            "categories": {"action_shot": 5, "portrait": 5},
        }
        output_path = self.store.export_dict(data, "summary.json")

        self.assertTrue(output_path.exists())
        with open(output_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["summary"]["total"], 10)

    def test_atomic_write_partial_failure(self) -> None:
        result = build_result("test.jpg")

        valid_file = Path(self.temp_dir) / "valid.json"
        self.store._write_json(valid_file, result.to_dict())
        self.assertTrue(valid_file.exists())

        temp_files = [f for f in os.listdir(self.temp_dir) if f.endswith(".tmp")]
        self.assertEqual(len(temp_files), 0)


class TestAtomicWrites(unittest.TestCase):
    """Test atomic write behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.store = JSONStore(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_temp_files_after_successful_write(self) -> None:
        output_file = Path(self.temp_dir) / "test.json"
        self.store._write_json(output_file, {"test": "data"})

        self.assertTrue(output_file.exists())
        temp_files = [f for f in os.listdir(self.temp_dir) if f.endswith(".tmp")]
        self.assertEqual(len(temp_files), 0)

    def test_file_content_is_complete(self) -> None:
        output_file = Path(self.temp_dir) / "complete.json"
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        self.store._write_json(output_file, data)

        with open(output_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_overwrite_existing_file(self) -> None:
        output_file = Path(self.temp_dir) / "overwrite.json"

        self.store._write_json(output_file, {"version": 1})
        self.store._write_json(output_file, {"version": 2})

        with open(output_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["version"], 2)


if __name__ == "__main__":
    unittest.main()
