"""Batch tracking utilities for photo analysis operations.

Provides BatchResult dataclass for capturing batch outcomes and
BatchTracker class for incrementally tracking progress during processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import json
from pathlib import Path

# Graceful import for structlog - falls back to standard logging
import logging

HAS_STRUCTLOG = False
structlog: Any = None

try:
    import structlog as _structlog

    structlog = _structlog
    HAS_STRUCTLOG = True
except ImportError:
    pass


def _get_logger(name: str) -> Any:
    """Get appropriate logger based on availability."""
    if HAS_STRUCTLOG and structlog is not None:
        return structlog.get_logger(name)
    return logging.getLogger(name)


@dataclass
class BatchResult:
    """Complete result of a batch processing operation.

    Captures counts, timing, and error details for batch operations.

    Attributes:
        batch_id: Unique identifier for this batch
        total: Total number of items to process
        processed: Number of items actually processed
        succeeded: Number of successful operations
        failed: Number of failed operations
        skipped: Number of skipped items
        errors: List of error dictionaries with context
        start_time: When batch processing started
        end_time: When batch processing completed
    """

    batch_id: str
    total: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage (0-100).

        Returns 0.0 if no items were processed.
        """
        if self.processed == 0:
            return 0.0
        return (self.succeeded / self.processed) * 100.0

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration in seconds.

        Returns 0.0 if batch hasn't finished.
        """
        if self.end_time is None:
            return 0.0
        delta = self.end_time - self.start_time
        return delta.total_seconds()

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage (0-100)."""
        if self.processed == 0:
            return 0.0
        return (self.failed / self.processed) * 100.0

    @property
    def is_complete(self) -> bool:
        """Check if batch processing is complete."""
        return self.end_time is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "batch_id": self.batch_id,
            "total": self.total,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "duration_seconds": self.duration_seconds,
            "is_complete": self.is_complete,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchResult":
        """Create BatchResult from dictionary."""
        return cls(
            batch_id=data["batch_id"],
            total=data.get("total", 0),
            processed=data.get("processed", 0),
            succeeded=data.get("succeeded", 0),
            failed=data.get("failed", 0),
            skipped=data.get("skipped", 0),
            errors=data.get("errors", []),
            start_time=datetime.fromisoformat(data["start_time"])
            if "start_time" in data
            else datetime.now(),
            end_time=datetime.fromisoformat(data["end_time"])
            if data.get("end_time")
            else None,
        )

    def export_to_jsonl(self, path: str | Path) -> None:
        """Export result as a single line in JSONL format.

        Appends to existing file if present.

        Args:
            path: File path to write to (will be created if needed)
        """
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict()) + "\n")


class BatchTracker:
    """Incremental tracker for batch processing operations.

    Records successes, failures, and skips during processing,
    then produces a BatchResult on completion.

    Example:
        >>> tracker = BatchTracker(batch_id="batch_001")
        >>> tracker.start_batch(total=10)
        >>> tracker.record_success()
        >>> tracker.record_failure(error="File not found", photo_path="/img/1.jpg")
        >>> result = tracker.finish_batch()
        >>> result.success_rate
        50.0
    """

    def __init__(self, batch_id: str):
        """Initialize tracker with a batch identifier.

        Args:
            batch_id: Unique identifier for this batch
        """
        self._batch_id = batch_id
        self._total = 0
        self._processed = 0
        self._succeeded = 0
        self._failed = 0
        self._skipped = 0
        self._errors: list[dict[str, Any]] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._logger = _get_logger(f"batch_tracker.{batch_id}")
        self._finished = False

    @property
    def batch_id(self) -> str:
        """Get the batch identifier."""
        return self._batch_id

    @property
    def total(self) -> int:
        """Get total items in batch."""
        return self._total

    @property
    def processed(self) -> int:
        """Get number of processed items."""
        return self._processed

    @property
    def succeeded(self) -> int:
        """Get number of successful items."""
        return self._succeeded

    @property
    def failed(self) -> int:
        """Get number of failed items."""
        return self._failed

    @property
    def remaining(self) -> int:
        """Get number of remaining items."""
        return max(0, self._total - self._processed)

    def start_batch(self, total: int) -> None:
        """Initialize batch processing with total item count.

        Args:
            total: Total number of items to process
        """
        self._total = total
        self._start_time = datetime.now()
        self._finished = False
        self._log_progress("batch_started", total=total)

    def record_success(self, photo_path: Optional[str] = None) -> None:
        """Record a successful processing operation.

        Args:
            photo_path: Optional path to the processed photo
        """
        self._succeeded += 1
        self._processed += 1
        self._log_progress(
            "success",
            photo_path=photo_path,
            succeeded=self._succeeded,
            processed=self._processed,
            total=self._total,
        )

    def record_failure(
        self,
        error: str,
        photo_path: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Record a failed processing operation.

        Args:
            error: Error message describing the failure
            photo_path: Optional path to the photo that failed
            exception: Optional exception object for additional context
        """
        error_record: dict[str, Any] = {
            "photo_path": photo_path,
            "error_message": error,
            "timestamp": datetime.now().isoformat(),
        }
        if exception is not None:
            error_record["exception_type"] = type(exception).__name__
            error_record["exception_message"] = str(exception)

        self._errors.append(error_record)
        self._failed += 1
        self._processed += 1
        self._log_progress(
            "failure",
            photo_path=photo_path,
            error=error,
            failed=self._failed,
            processed=self._processed,
            total=self._total,
        )

    def record_skip(self, photo_path: Optional[str] = None, reason: str = "") -> None:
        """Record a skipped item.

        Args:
            photo_path: Optional path to the skipped photo
            reason: Optional reason for skipping
        """
        self._skipped += 1
        self._processed += 1
        self._log_progress(
            "skip",
            photo_path=photo_path,
            reason=reason,
            skipped=self._skipped,
            processed=self._processed,
            total=self._total,
        )

    def finish_batch(self) -> BatchResult:
        """Complete batch processing and return final result.

        Returns:
            BatchResult with all recorded metrics and errors
        """
        self._end_time = datetime.now()
        self._finished = True

        result = BatchResult(
            batch_id=self._batch_id,
            total=self._total,
            processed=self._processed,
            succeeded=self._succeeded,
            failed=self._failed,
            skipped=self._skipped,
            errors=self._errors.copy(),
            start_time=self._start_time or datetime.now(),
            end_time=self._end_time,
        )

        self._log_progress(
            "batch_finished",
            success_rate=result.success_rate,
            duration_seconds=result.duration_seconds,
            total=self._total,
            succeeded=self._succeeded,
            failed=self._failed,
            skipped=self._skipped,
        )

        return result

    def _log_progress(self, event: str, **kwargs: Any) -> None:
        """Log progress using structlog or standard logging."""
        if HAS_STRUCTLOG:
            self._logger.info(event, batch_id=self._batch_id, **kwargs)
        else:
            msg = f"[{self._batch_id}] {event}"
            if kwargs:
                msg += f" {kwargs}"
            self._logger.info(msg)

    def get_current_result(self) -> BatchResult:
        """Get current result without finishing the batch.

        Useful for progress reporting during long-running batches.

        Returns:
            BatchResult with current metrics (end_time will be None)
        """
        return BatchResult(
            batch_id=self._batch_id,
            total=self._total,
            processed=self._processed,
            succeeded=self._succeeded,
            failed=self._failed,
            skipped=self._skipped,
            errors=self._errors.copy(),
            start_time=self._start_time or datetime.now(),
            end_time=None,
        )
