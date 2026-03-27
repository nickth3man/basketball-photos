from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from PIL import Image

from src.scraper.downloader import Downloader
from src.scraper.sources import SourceCandidate


def build_candidate(
    title: str, url: str = "https://example.com/image.jpg"
) -> SourceCandidate:
    return SourceCandidate(
        source="openverse",
        title=title,
        image_url=url,
        page_url="https://example.com/page",
        license="by",
        creator="Alex",
        width=1600,
        height=1200,
    )


def build_image_bytes(format_name: str = "JPEG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=(120, 80, 200)).save(buffer, format=format_name)
    return buffer.getvalue()


class TestDownloader(unittest.TestCase):
    def setUp(self) -> None:
        self.downloader = Downloader()

    def _mock_response(
        self,
        *,
        content_type: str,
        body: bytes,
        status_error: Exception | None = None,
    ) -> MagicMock:
        response = MagicMock()
        response.headers = {"Content-Type": content_type}
        response.iter_content.return_value = [body]
        if status_error is None:
            response.raise_for_status.return_value = None
        else:
            response.raise_for_status.side_effect = status_error
        return response

    def test_download_streams_image_to_disk(self) -> None:
        candidate = build_candidate("Accepted Photo")
        response = self._mock_response(
            content_type="image/jpeg",
            body=build_image_bytes(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(self.downloader.session, "get", return_value=response):
                file_path = self.downloader.download(candidate, tmpdir)

            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.suffix, ".jpg")

    def test_download_rejects_unsupported_content_type(self) -> None:
        candidate = build_candidate("Not An Image")
        response = self._mock_response(content_type="text/html", body=b"<html />")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(self.downloader.session, "get", return_value=response):
                with self.assertRaises(ValueError):
                    self.downloader.download(candidate, tmpdir)

    def test_download_adds_suffix_when_slug_collides(self) -> None:
        candidate = build_candidate("Repeated Title")
        response = self._mock_response(
            content_type="image/jpeg",
            body=build_image_bytes(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            existing = Path(tmpdir) / "repeated-title-openverse.jpg"
            existing.write_bytes(b"existing")

            with patch.object(self.downloader.session, "get", return_value=response):
                file_path = self.downloader.download(candidate, tmpdir)

            self.assertEqual(file_path.name, "repeated-title-openverse-2.jpg")

    def test_download_raises_http_failures(self) -> None:
        candidate = build_candidate("HTTP Failure")
        response = self._mock_response(
            content_type="image/jpeg",
            body=b"",
            status_error=requests.HTTPError("bad response"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(self.downloader.session, "get", return_value=response):
                with self.assertRaises(requests.HTTPError):
                    self.downloader.download(candidate, tmpdir)

    def test_download_rejects_invalid_image_signature(self) -> None:
        candidate = build_candidate("Broken Image")
        response = self._mock_response(
            content_type="image/jpeg",
            body=b"not-really-an-image",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(self.downloader.session, "get", return_value=response):
                with self.assertRaises(ValueError):
                    self.downloader.download(candidate, tmpdir)


if __name__ == "__main__":
    unittest.main()
