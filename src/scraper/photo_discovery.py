from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

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
    max_retries_per_source = 3
    max_failures_per_source = 3

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

        profile = self.comparator.build_profile(reference_results)
        threshold = self.threshold_manager.determine_threshold(profile, strategy)
        target_dir = Path(output_dir or self.config.discovery.download_dir)
        queries = self._build_queries(profile)

        accepted: list[dict[str, object]] = []
        reviewed: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        source_failures: dict[str, int] = {
            type(source).__name__: 0 for source in self.sources
        }

        for query in queries:
            for source in self.sources:
                source_name = type(source).__name__
                if source_failures[source_name] >= self.max_failures_per_source:
                    logger.warning(
                        "Skipping source %s after repeated failures", source_name
                    )
                    continue

                try:
                    candidates = source.search(query, limit=max(count * 2, 10))
                except Exception as error:  # noqa: BLE001
                    source_failures[source_name] = min(
                        source_failures[source_name] + 1, self.max_retries_per_source
                    )
                    logger.warning(
                        "Source search failed for %s: %s", source_name, error
                    )
                    continue

                for candidate in candidates:
                    if (
                        candidate.image_url in seen_urls
                        or not self._has_allowed_license(candidate)
                    ):
                        continue
                    seen_urls.add(candidate.image_url)

                    if not self._meets_min_resolution(candidate):
                        continue

                    record = self._process_candidate(
                        candidate,
                        profile,
                        strategy,
                        threshold,
                        target_dir,
                        source_name,
                        source_failures,
                    )
                    if record is None:
                        continue

                    comparison: dict[str, Any] | None = record.get("comparison")  # type: ignore[assignment]
                    is_accepted = (
                        comparison is not None
                        and comparison.get("accepted", False) is True  # type: ignore[arg-type]
                    )

                    if is_accepted:
                        accepted.append(record)
                    else:
                        reviewed.append(record)

                    if source_failures[source_name] >= self.max_failures_per_source:
                        break

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

        return self._finalize_manifest(
            profile, strategy, threshold, queries, accepted, reviewed
        )

    def _process_candidate(
        self,
        candidate: SourceCandidate,
        profile: BenchmarkProfile,
        strategy: str,
        threshold: float,
        target_dir: Path,
        source_name: str,
        source_failures: dict[str, int],
    ) -> dict[str, object] | None:
        downloaded_path: Path | None = None

        try:
            downloaded_path = self.downloader.download(candidate, target_dir)
        except Exception as error:  # noqa: BLE001
            return self._build_failure_record(
                candidate,
                strategy,
                threshold,
                reject_reason="download_failed",
                error=error,
                source_name=source_name,
                source_failures=source_failures,
            )

        try:
            result = self.analyzer.analyze_file(
                downloaded_path,
                context_text=candidate.build_context_text(),
            )
        except Exception as error:  # noqa: BLE001
            downloaded_path.unlink(missing_ok=True)
            return self._build_failure_record(
                candidate,
                strategy,
                threshold,
                reject_reason="analysis_failed",
                error=error,
                file_path=downloaded_path,
                source_name=source_name,
                source_failures=source_failures,
            )

        if not self._meets_downloaded_min_resolution(result):
            downloaded_path.unlink(missing_ok=True)
            return {
                "candidate": candidate.to_dict(),
                "analysis": result.to_dict(),
                "comparison": {
                    "accepted": False,
                    "strategy": strategy,
                    "threshold": threshold,
                    "overall_score": result.scores.overall_score,
                    "gap": round(result.scores.overall_score - threshold, 2),
                    "category_match": False,
                    "tag_overlap": [],
                    "reject_reason": "downloaded_image_below_min_resolution",
                },
                "file_path": str(downloaded_path),
            }

        comparison = self.comparator.evaluate_candidate(
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
            try:
                with PhotoDatabase(self.config.output.database) as database:
                    database.save_analysis(result)
            except Exception as error:  # noqa: BLE001
                source_failures[source_name] = min(
                    source_failures[source_name] + 1, self.max_retries_per_source
                )
                downloaded_path.unlink(missing_ok=True)
                return self._build_failure_record(
                    candidate,
                    strategy,
                    threshold,
                    reject_reason="persistence_failed",
                    error=error,
                    analysis=result,
                    file_path=downloaded_path,
                    source_name=source_name,
                    source_failures=source_failures,
                )
        else:
            downloaded_path.unlink(missing_ok=True)

        source_failures[source_name] = 0
        return record

    def _build_failure_record(
        self,
        candidate: SourceCandidate,
        strategy: str,
        threshold: float,
        *,
        reject_reason: str,
        error: Exception,
        source_name: str,
        source_failures: dict[str, int],
        analysis: AnalysisResult | None = None,
        file_path: Path | None = None,
    ) -> dict[str, object]:
        source_failures[source_name] = min(
            source_failures[source_name] + 1, self.max_retries_per_source
        )
        logger.warning(
            "Skipping discovery candidate %s: %s", candidate.image_url, error
        )

        return {
            "candidate": candidate.to_dict(),
            "analysis": analysis.to_dict() if analysis is not None else None,
            "comparison": {
                "accepted": False,
                "strategy": strategy,
                "threshold": threshold,
                "overall_score": analysis.scores.overall_score if analysis else None,
                "gap": (
                    round(analysis.scores.overall_score - threshold, 2)
                    if analysis is not None
                    else None
                ),
                "category_match": False,
                "tag_overlap": [],
                "reject_reason": reject_reason,
                "error": str(error),
            },
            "file_path": str(file_path) if file_path is not None else None,
        }

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
        queries.extend(
            category_terms.get(category, "basketball editorial photo")
            for category, _count in sorted(
                profile.category_distribution.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )
        if "archival-look" in profile.top_tags:
            queries.append("vintage basketball photo")
        if "portrait-orientation" in profile.top_tags:
            queries.append("basketball portrait vertical")
        return list(dict.fromkeys(queries))

    def _has_allowed_license(self, candidate: SourceCandidate) -> bool:
        normalized = candidate.license.lower()
        return any(allowed in normalized for allowed in self.allowed_licenses)

    def _meets_min_resolution(self, candidate: SourceCandidate) -> bool:
        if candidate.width is None or candidate.height is None:
            return True
        return (
            candidate.width >= self.config.analysis.min_width
            and candidate.height >= self.config.analysis.min_height
        )

    def _meets_downloaded_min_resolution(self, result: AnalysisResult) -> bool:
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
