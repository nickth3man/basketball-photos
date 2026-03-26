import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.types.analysis import AnalysisResult

logger = logging.getLogger(__name__)


class JSONStore:
    """JSON export for analysis results."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def export_single(
        self, result: AnalysisResult, filename: str | None = None
    ) -> None:
        export_name = filename or result.metadata.filename
        output_file = self.output_path / export_name
        output_file = output_file.with_suffix(".json")

        self._write_json(output_file, result.to_dict())
        logger.info(f"Exported analysis to {output_file}")

    def export_batch(
        self, results: list[AnalysisResult], filename: str = "analysis_results.json"
    ) -> None:
        output_file = self.output_path / filename

        self.output_path.mkdir(parents=True, exist_ok=True)

        data = {
            "exported_at": datetime.now().isoformat(),
            "total_photos": len(results),
            "results": [r.to_dict() for r in results],
        }

        self._write_json(output_file, data)
        logger.info(f"Exported {len(results)} results to {output_file}")

    def _write_json(self, filepath: Path, data: dict[str, Any]) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(
            dir=filepath.parent,
            prefix=filepath.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, filepath)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        logger.debug(f"Wrote JSON to {filepath}")

    def load_batch(
        self, filename: str = "analysis_results.json"
    ) -> list[dict[str, Any]] | None:
        input_file = self.output_path / filename

        if not input_file.exists():
            logger.warning(f"File not found: {input_file}")
            return []

        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        results = data.get("results", [])
        logger.info(f"Loaded {len(results)} results from {input_file}")
        return results

    def export_dict(self, data: dict[str, Any], filename: str) -> Path:
        output_file = self.output_path / filename
        self._write_json(output_file, data)
        logger.info(f"Exported structured data to {output_file}")
        return output_file
