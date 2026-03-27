"""Review queue export functionality for player identification.

Provides utilities to export photos needing manual review to JSON/CSV
for human review and correction.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ReviewItem:
    """Single item in the review queue.

    Represents a player identity that needs manual review.
    """

    photo_path: str
    photo_filename: str
    player_name: str
    jersey_number: str
    team: str
    confidence: float
    detected_bbox: list[int] = field(default_factory=list)
    suggested_player_id: int | None = None
    suggested_player_name: str = ""
    review_status: str = "needs_review"
    reviewer_notes: str = ""
    reviewed_at: str = ""
    reviewer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "photo_path": self.photo_path,
            "photo_filename": self.photo_filename,
            "player_name": self.player_name,
            "jersey_number": self.jersey_number,
            "team": self.team,
            "confidence": self.confidence,
            "detected_bbox": self.detected_bbox,
            "suggested_player_id": self.suggested_player_id,
            "suggested_player_name": self.suggested_player_name,
            "review_status": self.review_status,
            "reviewer_notes": self.reviewer_notes,
            "reviewed_at": self.reviewed_at,
            "reviewer_id": self.reviewer_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewItem":
        return cls(
            photo_path=data["photo_path"],
            photo_filename=data["photo_filename"],
            player_name=data["player_name"],
            jersey_number=data["jersey_number"],
            team=data["team"],
            confidence=data["confidence"],
            detected_bbox=data.get("detected_bbox", []),
            suggested_player_id=data.get("suggested_player_id"),
            suggested_player_name=data.get("suggested_player_name", ""),
            review_status=data.get("review_status", "needs_review"),
            reviewer_notes=data.get("reviewer_notes", ""),
            reviewed_at=data.get("reviewed_at", ""),
            reviewer_id=data.get("reviewer_id", ""),
        )


class ReviewQueueExporter:
    """Export photos needing player identity review to external formats.

    Provides export to JSON and CSV for human review workflows.
    """

    def __init__(self, output_dir: str | Path = "./reviews"):
        """Initialize the review queue exporter.

        Args:
            output_dir: Directory for review queue exports.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_to_json(
        self,
        review_items: list[ReviewItem],
        filename: str | None = None,
    ) -> Path:
        """Export review items to JSON file.

        Args:
            review_items: List of items needing review.
            filename: Optional filename, defaults to timestamped name.

        Returns:
            Path to exported file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"review_queue_{timestamp}.json"

        output_path = self.output_dir / filename

        data = {
            "exported_at": datetime.now().isoformat(),
            "total_items": len(review_items),
            "items": [item.to_dict() for item in review_items],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(review_items)} items to {output_path}")
        return output_path

    def export_to_csv(
        self,
        review_items: list[ReviewItem],
        filename: str | None = None,
    ) -> Path:
        """Export review items to CSV file.

        Args:
            review_items: List of items needing review.
            filename: Optional filename, defaults to timestamped name.

        Returns:
            Path to exported file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"review_queue_{timestamp}.csv"

        output_path = self.output_dir / filename

        if not review_items:
            with open(output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "photo_path",
                        "photo_filename",
                        "player_name",
                        "jersey_number",
                        "team",
                        "confidence",
                        "detected_bbox",
                        "suggested_player_id",
                        "suggested_player_name",
                        "review_status",
                        "reviewer_notes",
                        "reviewed_at",
                        "reviewer_id",
                    ]
                )
            return output_path

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=review_items[0].to_dict().keys())
            writer.writeheader()
            for item in review_items:
                writer.writerow(item.to_dict())

        logger.info(f"Exported {len(review_items)} items to {output_path}")
        return output_path

    def load_from_json(self, filepath: str | Path) -> list[ReviewItem]:
        """Load review items from JSON file.

        Args:
            filepath: Path to JSON file.

        Returns:
            List of ReviewItem objects.
        """
        with open(filepath) as f:
            data = json.load(f)

        items = [ReviewItem.from_dict(item) for item in data.get("items", [])]
        logger.info(f"Loaded {len(items)} items from {filepath}")
        return items

    def load_from_csv(self, filepath: str | Path) -> list[ReviewItem]:
        """Load review items from CSV file.

        Args:
            filepath: Path to CSV file.

        Returns:
            List of ReviewItem objects.
        """
        items = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(ReviewItem.from_dict(row))

        logger.info(f"Loaded {len(items)} items from {filepath}")
        return items


def create_review_queue(
    results: list[Any],
    confidence_threshold: float = 0.85,
) -> list[ReviewItem]:
    """Create review queue from analysis results.

    Args:
        results: List of AnalysisResult objects.
        confidence_threshold: Minimum confidence for auto-approval.

    Returns:
        List of ReviewItem objects needing review.
    """
    review_items = []

    for result in results:
        if not result.player_identities:
            continue

        for identity in result.player_identities:
            if identity.review_status == "needs_review":
                review_items.append(
                    ReviewItem(
                        photo_path=result.metadata.path,
                        photo_filename=result.metadata.filename,
                        player_name=identity.name,
                        jersey_number=identity.jersey_number,
                        team=identity.team,
                        confidence=identity.confidence,
                        detected_bbox=identity.bbox,
                        suggested_player_id=identity.player_id,
                        suggested_player_name=identity.name,
                        review_status="needs_review",
                    )
                )

    logger.info(f"Created review queue with {len(review_items)} items")
    return review_items
