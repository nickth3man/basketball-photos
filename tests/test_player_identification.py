"""Tests for PlayerIdentity dataclass."""

import pytest

from src.types.player_identification import PlayerDetectionResult, PlayerIdentity


class TestPlayerIdentity:
    """Test cases for PlayerIdentity dataclass."""

    def test_basic_creation(self):
        """Test creating a PlayerIdentity with valid data."""
        identity = PlayerIdentity(
            player_id=2544,
            name="LeBron James",
            jersey_number="23",
            team="LAL",
            confidence=0.92,
            detection_confidence=0.95,
            ocr_confidence=0.88,
            bbox=[100, 200, 300, 400],
            review_status="auto_approved",
            method="jersey_ocr",
        )

        assert identity.player_id == 2544
        assert identity.name == "LeBron James"
        assert identity.jersey_number == "23"
        assert identity.team == "LAL"
        assert identity.confidence == 0.92
        assert identity.is_high_confidence is True
        assert identity.needs_review is False

    def test_needs_review_status(self):
        """Test needs_review property with different confidences."""
        high = PlayerIdentity(
            player_id=1,
            name="Test",
            jersey_number="1",
            team="LAL",
            confidence=0.9,
            detection_confidence=0.9,
            ocr_confidence=0.9,
            bbox=[0, 0, 100, 100],
            review_status="auto_approved",
            method="jersey_ocr",
        )
        assert high.needs_review is False
        assert high.identification_tier == "auto_approved"

        medium = PlayerIdentity(
            player_id=1,
            name="Test",
            jersey_number="1",
            team="LAL",
            confidence=0.7,
            detection_confidence=0.7,
            ocr_confidence=0.7,
            bbox=[0, 0, 100, 100],
            review_status="needs_review",
            method="jersey_ocr",
        )
        assert medium.needs_review is True
        assert medium.identification_tier == "needs_review"

    def test_serialization(self):
        """Test to_dict and from_dict roundtrip."""
        original = PlayerIdentity(
            player_id=2544,
            name="LeBron James",
            jersey_number="23",
            team="LAL",
            confidence=0.92,
            detection_confidence=0.95,
            ocr_confidence=0.88,
            bbox=[100, 200, 300, 400],
            review_status="auto_approved",
            method="jersey_ocr",
        )

        data = original.to_dict()
        restored = PlayerIdentity.from_dict(data)

        assert restored.player_id == original.player_id
        assert restored.name == original.name
        assert restored.bbox == original.bbox


class TestPlayerDetectionResult:
    """Test cases for PlayerDetectionResult dataclass."""

    def test_basic_creation(self):
        """Test creating a detection result."""
        identities = [
            PlayerIdentity(
                player_id=2544,
                name="LeBron James",
                jersey_number="23",
                team="LAL",
                confidence=0.92,
                detection_confidence=0.95,
                ocr_confidence=0.88,
                bbox=[100, 200, 300, 400],
                review_status="auto_approved",
                method="jersey_ocr",
            )
        ]

        result = PlayerDetectionResult(
            photo_path="test.jpg",
            photo_id=1,
            detections=identities,
            processing_time_ms=150.0,
            model_version="1.0.0",
        )

        assert result.photo_path == "test.jpg"
        assert len(result.detections) == 1
        assert result.processing_time_ms == 150.0
