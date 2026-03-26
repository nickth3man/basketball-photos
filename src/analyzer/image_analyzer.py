from __future__ import annotations

import logging
from pathlib import Path

from src.analyzer.grading_rubric import GradingRubric
from src.analyzer.metadata_extractor import MetadataExtractor
from src.categorizer.classifier import Classifier
from src.categorizer.tagger import Tagger
from src.config import load_config
from src.storage.database import PhotoDatabase
from src.storage.json_store import JSONStore
from src.types.analysis import AnalysisResult
from src.types.config import Config

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self.metadata_extractor = MetadataExtractor()
        self.rubric = GradingRubric(self.config.weights)
        self.classifier = Classifier(self.config.categories)
        self.tagger = Tagger()

    def analyze_file(
        self,
        image_path: str | Path,
        *,
        context_text: str | None = None,
    ) -> AnalysisResult:
        metadata = self.metadata_extractor.extract(image_path)
        scores = self.rubric.score_image(image_path, context_text=context_text)
        category = self.classifier.classify(
            metadata,
            scores,
            context_text=context_text,
        )
        tags = self.tagger.build_tags(
            metadata, scores, category, context_text=context_text
        )
        return AnalysisResult(
            metadata=metadata, scores=scores, category=category, tags=tags
        )

    def analyze_directory(
        self,
        directory: str | Path,
        *,
        recursive: bool = False,
        persist: bool = True,
    ) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        for metadata in self.metadata_extractor.extract_batch(
            directory, recursive=recursive
        ):
            result = self.analyze_file(metadata.path, context_text=metadata.filename)
            results.append(result)

        if persist:
            self.persist_results(results)
        return results

    def persist_results(self, results: list[AnalysisResult]) -> None:
        if not results:
            return

        with PhotoDatabase(self.config.output.database) as database:
            for result in results:
                database.save_analysis(result)

        store = JSONStore(self.config.output.reports_dir)
        store.export_batch(results)

    def summarize(self, results: list[AnalysisResult]) -> dict[str, object]:
        if not results:
            return {
                "total_photos": 0,
                "average_score": 0.0,
                "best_photo": None,
                "worst_photo": None,
                "categories": {},
            }

        ordered = sorted(
            results, key=lambda result: result.scores.overall_score, reverse=True
        )
        categories: dict[str, int] = {}
        for result in results:
            categories[result.category] = categories.get(result.category, 0) + 1

        average_score = round(
            sum(result.scores.overall_score for result in results) / len(results), 2
        )

        return {
            "total_photos": len(results),
            "average_score": average_score,
            "best_photo": {
                "filename": ordered[0].metadata.filename,
                "overall_score": ordered[0].scores.overall_score,
            },
            "worst_photo": {
                "filename": ordered[-1].metadata.filename,
                "overall_score": ordered[-1].scores.overall_score,
            },
            "categories": categories,
        }
