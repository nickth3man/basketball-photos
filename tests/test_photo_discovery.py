from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from src.scraper.photo_discovery import PhotoDiscovery
from src.scraper.sources import SourceCandidate
from src.types.analysis import AnalysisResult
from src.types.config import Config
from src.types.photo import PhotoMetadata
from src.types.scores import PhotoScore


def build_result(
    path: str,
    overall_score: float,
    *,
    width: int = 1600,
    height: int = 1200,
    category: str = "action_shot",
    tags: list[str] | None = None,
) -> AnalysisResult:
    metadata = PhotoMetadata(
        path=path,
        filename=Path(path).name,
        width=width,
        height=height,
        format="JPEG",
        file_size=1000,
        color_mode="RGB",
    )
    score = PhotoScore(
        resolution_clarity=overall_score,
        composition=overall_score,
        action_moment=overall_score,
        lighting=overall_score,
        color_quality=overall_score,
        subject_isolation=overall_score,
        emotional_impact=overall_score,
        technical_quality=overall_score,
        relevance=overall_score,
        instagram_suitability=overall_score,
        weights={},
    )
    return AnalysisResult(
        metadata=metadata, scores=score, category=category, tags=tags or ["high-action"]
    )


def build_candidate(title: str, image_url: str) -> SourceCandidate:
    return SourceCandidate(
        source="openverse",
        title=title,
        image_url=image_url,
        page_url=f"{image_url}/page",
        license="by",
        creator="Alex",
        width=1600,
        height=1200,
    )


class StaticSource:
    def __init__(self, candidates: list[SourceCandidate]):
        self.candidates = candidates

    def search(self, query: str, limit: int = 10) -> list[SourceCandidate]:
        return self.candidates[:limit]


class TestPhotoDiscovery(unittest.TestCase):
    def _build_config(self, root: Path) -> Config:
        config = Config()
        config.discovery.rate_limit = 0
        config.discovery.download_dir = str(root / "downloads")
        config.output.database = str(root / "data" / "photo_grades.db")
        config.output.reports_dir = str(root / "reports")
        return config

    def test_discover_requires_reference_results(self) -> None:
        discovery = PhotoDiscovery(Config())

        with self.assertRaises(ValueError):
            discovery.discover([], count=1)

    def test_discover_deduplicates_and_splits_accepted_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discovery = PhotoDiscovery(self._build_config(root))
            discovery._build_queries = lambda profile: ["query"]
            discovery.sources = [
                StaticSource(
                    [
                        build_candidate("accepted", "https://example.com/1.jpg"),
                        build_candidate("duplicate", "https://example.com/1.jpg"),
                        build_candidate("reviewed", "https://example.com/2.jpg"),
                    ]
                )
            ]

            def fake_download(
                candidate: SourceCandidate, target_dir: str | Path
            ) -> Path:
                path = Path(target_dir) / f"{candidate.title}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fake")
                return path

            def fake_analyze(
                image_path: str | Path, context_text: str | None = None
            ) -> AnalysisResult:
                image_path = Path(image_path)
                if "accepted" in image_path.name:
                    return build_result(str(image_path), 8.0)
                return build_result(str(image_path), 6.0)

            with (
                patch.object(
                    discovery.downloader, "download", side_effect=fake_download
                ),
                patch.object(
                    discovery.analyzer, "analyze_file", side_effect=fake_analyze
                ),
            ):
                manifest = discovery.discover(
                    [build_result("reference.jpg", 7.0)], count=2
                )

            accepted = cast(list[dict[str, object]], manifest["accepted"])
            reviewed = cast(list[dict[str, object]], manifest["reviewed"])
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(reviewed), 1)
            accepted_path = Path(cast(str, accepted[0]["file_path"]))
            reviewed_path = Path(cast(str, reviewed[0]["file_path"]))
            self.assertTrue(accepted_path.exists())
            self.assertFalse(reviewed_path.exists())

    def test_discover_cleans_up_after_analysis_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discovery = PhotoDiscovery(self._build_config(root))
            discovery._build_queries = lambda profile: ["query"]
            discovery.sources = [
                StaticSource(
                    [build_candidate("broken", "https://example.com/broken.jpg")]
                )
            ]

            def fake_download(
                candidate: SourceCandidate, target_dir: str | Path
            ) -> Path:
                path = Path(target_dir) / f"{candidate.title}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fake")
                return path

            with (
                patch.object(
                    discovery.downloader, "download", side_effect=fake_download
                ),
                patch.object(
                    discovery.analyzer,
                    "analyze_file",
                    side_effect=RuntimeError("analysis boom"),
                ),
            ):
                manifest = discovery.discover(
                    [build_result("reference.jpg", 7.0)], count=1
                )

            accepted = cast(list[dict[str, object]], manifest["accepted"])
            reviewed = cast(list[dict[str, object]], manifest["reviewed"])
            self.assertEqual(accepted, [])
            self.assertEqual(len(reviewed), 1)
            comparison = cast(dict[str, object], reviewed[0]["comparison"])
            self.assertEqual(comparison["reject_reason"], "analysis_failed")
            self.assertFalse(Path(root / "downloads" / "broken.jpg").exists())

    def test_discover_stops_processing_after_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discovery = PhotoDiscovery(self._build_config(root))
            discovery._build_queries = lambda profile: ["query"]
            discovery.sources = [
                StaticSource(
                    [
                        build_candidate("one", "https://example.com/1.jpg"),
                        build_candidate("two", "https://example.com/2.jpg"),
                        build_candidate("three", "https://example.com/3.jpg"),
                        build_candidate("four", "https://example.com/4.jpg"),
                    ]
                )
            ]

            with patch.object(
                discovery.downloader,
                "download",
                side_effect=RuntimeError("download boom"),
            ):
                manifest = discovery.discover(
                    [build_result("reference.jpg", 7.0)], count=1
                )

            accepted = cast(list[dict[str, object]], manifest["accepted"])
            reviewed = cast(list[dict[str, object]], manifest["reviewed"])
            self.assertEqual(accepted, [])
            self.assertEqual(len(reviewed), discovery.source_circuit_breaker)


if __name__ == "__main__":
    unittest.main()
