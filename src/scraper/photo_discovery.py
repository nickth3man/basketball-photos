from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

from src.analyzer.image_analyzer import ImageAnalyzer
from src.config import load_config
from src.grader.comparator import BenchmarkProfile, Comparator
from src.grader.threshold_manager import ThresholdManager
from src.scraper.downloader import Downloader
from src.scraper.sources import OpenverseSource, SourceCandidate, WikimediaCommonsSource
from src.storage.database import PhotoDatabase
from src.storage.json_store import JSONStore
from src.types.analysis import AnalysisResult
from src.types.config import Config

logger = logging.getLogger(__name__)


class PhotoDiscovery:
    allowed_licenses = {
        "cc0",
        "by",
        "by-sa",
        "pdm",
        "public domain",
        "cc by",
        "cc by-sa",
    }

    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self.analyzer = ImageAnalyzer(self.config)
        self.comparator = Comparator()
        self.threshold_manager = ThresholdManager()
        self.downloader = Downloader()
        self.sources = [OpenverseSource(), WikimediaCommonsSource()]

    def discover(
        self,
        reference_results: list[AnalysisResult],
        *,
        count: int,
        strategy: str = "all",
        output_dir: str | Path | None = None,
    ) -> dict[str, object]:
        if not reference_results:
            raise ValueError("Reference results are required before discovery")

        # TODO: Add an end-to-end test module for discover() that covers empty
        # inputs, deduplication, accepted/reviewed splits, and cleanup paths.
        profile = self.comparator.build_profile(reference_results)
        threshold = self.threshold_manager.determine_threshold(profile, strategy)
        target_dir = Path(output_dir or self.config.discovery.download_dir)
        queries = self._build_queries(profile)

        accepted: list[dict[str, object]] = []
        reviewed: list[dict[str, object]] = []
        seen_urls: set[str] = set()

        for query in queries:
            for source in self.sources:
                for candidate in source.search(query, limit=max(count * 2, 10)):
                    if (
                        candidate.image_url in seen_urls
                        or not self._candidate_is_allowed(candidate)
                    ):
                        continue
                    seen_urls.add(candidate.image_url)

                    if not self._meets_resolution(candidate):
                        continue

                    try:
                        downloaded_path = self.downloader.download(
                            candidate, target_dir
                        )
                        result = self.analyzer.analyze_file(
                            downloaded_path,
                            context_text=candidate.context_text(),
                        )
                        if not self._meets_downloaded_resolution(result):
                            reviewed.append(
                                {
                                    "candidate": candidate.to_dict(),
                                    "analysis": result.to_dict(),
                                    "comparison": {
                                        "accepted": False,
                                        "strategy": strategy,
                                        "threshold": threshold,
                                        "overall_score": result.scores.overall_score,
                                        "gap": round(
                                            result.scores.overall_score - threshold, 2
                                        ),
                                        "category_match": False,
                                        "tag_overlap": [],
                                        "reject_reason": "downloaded_image_below_min_resolution",
                                    },
                                    "file_path": str(downloaded_path),
                                }
                            )
                            downloaded_path.unlink(missing_ok=True)
                            continue
                        comparison = self.comparator.compare(
                            result,
                            profile,
                            strategy=strategy,
                            threshold=threshold,
                        )
                        record = {
                            "candidate": candidate.to_dict(),
                            "analysis": result.to_dict(),
                            "comparison": comparison,
                            "file_path": str(downloaded_path),
                        }

                        if comparison["accepted"]:
                            accepted.append(record)
                            with PhotoDatabase(self.config.output.database) as database:
                                database.save_analysis(result)
                        else:
                            reviewed.append(record)
                            downloaded_path.unlink(missing_ok=True)

                        if len(accepted) >= count:
                            return self._finalize_manifest(
                                profile,
                                strategy,
                                threshold,
                                queries,
                                accepted,
                                reviewed,
                            )

                        time.sleep(self.config.discovery.rate_limit)
                    except Exception as error:  # noqa: BLE001
                        # TODO: Split download, analysis, and persistence
                        # failures into separate exception paths so retries and
                        # reporting can be tuned per failure mode.
                        # TODO: Add per-source retry budgets and a simple
                        # circuit-breaker threshold so repeated source failures
                        # do not burn the whole discovery run.
                        logger.warning(
                            "Skipping discovery candidate %s: %s",
                            candidate.image_url,
                            error,
                        )

        return self._finalize_manifest(
            profile, strategy, threshold, queries, accepted, reviewed
        )

    def _build_queries(self, profile: BenchmarkProfile) -> list[str]:
        category_terms = {
            "action_shot": "basketball action photo",
            "celebration": "basketball celebration photo",
            "portrait": "basketball player portrait",
            "iconic_moment": "historic basketball photo",
            "court_side": "basketball courtside photo",
            "team_photo": "basketball team photo",
        }
        queries = ["basketball photo", "basketball game photography"]
        for category, _count in sorted(
            profile.category_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            queries.append(category_terms.get(category, "basketball editorial photo"))
        if "archival-look" in profile.top_tags:
            queries.append("vintage basketball photo")
        if "portrait-orientation" in profile.top_tags:
            queries.append("basketball portrait vertical")
        return list(dict.fromkeys(queries))

    def _candidate_is_allowed(self, candidate: SourceCandidate) -> bool:
        normalized = candidate.license.lower()
        return any(allowed in normalized for allowed in self.allowed_licenses)

    def _meets_resolution(self, candidate: SourceCandidate) -> bool:
        if candidate.width is None or candidate.height is None:
            return True
        return (
            candidate.width >= self.config.analysis.min_width
            and candidate.height >= self.config.analysis.min_height
        )

    def _meets_downloaded_resolution(self, result: AnalysisResult) -> bool:
        return (
            result.metadata.width >= self.config.analysis.min_width
            and result.metadata.height >= self.config.analysis.min_height
        )

    def _finalize_manifest(
        self,
        profile: BenchmarkProfile,
        strategy: str,
        threshold: float,
        queries: Iterable[str],
        accepted: list[dict[str, object]],
        reviewed: list[dict[str, object]],
    ) -> dict[str, object]:
        manifest = {
            "benchmark": profile.to_dict(),
            "strategy": strategy,
            "threshold": threshold,
            "queries": list(queries),
            "accepted": accepted,
            "reviewed": reviewed,
        }
        JSONStore(self.config.output.reports_dir).export_dict(
            manifest, "discovery_results.json"
        )
        return manifest
