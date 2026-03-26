from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.scraper.sources import OpenverseSource, WikimediaCommonsSource


class DiscoverySourcesTest(unittest.TestCase):
    def test_openverse_source_maps_results(self) -> None:
        source = OpenverseSource()
        payload = {
            "results": [
                {
                    "title": "Basketball Action",
                    "url": "https://example.com/image.jpg",
                    "foreign_landing_url": "https://example.com/page",
                    "license": "by",
                    "creator": "Alex",
                    "width": 1600,
                    "height": 1200,
                    "tags": [{"name": "basketball"}],
                }
            ]
        }
        with patch.object(source, "_get") as mocked_get:
            mocked_response = MagicMock()
            mocked_response.json.return_value = payload
            mocked_get.return_value = mocked_response
            results = source.search("basketball", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "openverse")

    def test_openverse_source_skips_malformed_entries(self) -> None:
        source = OpenverseSource()
        payload = {
            "results": [
                "bad-entry",
                {"title": "Missing URL"},
                {
                    "title": "Basketball Action",
                    "thumbnail": "https://example.com/image.jpg",
                    "license": "by",
                    "creator": "Alex",
                },
            ]
        }
        with patch.object(source, "_get") as mocked_get:
            mocked_response = MagicMock()
            mocked_response.json.return_value = payload
            mocked_get.return_value = mocked_response
            results = source.search("basketball", limit=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].image_url, "https://example.com/image.jpg")

    def test_wikimedia_source_maps_results(self) -> None:
        source = WikimediaCommonsSource()
        payload = {
            "query": {
                "pages": {
                    "1": {
                        "title": "File:Basketball.jpg",
                        "fullurl": "https://commons.wikimedia.org/wiki/File:Basketball.jpg",
                        "categories": [{"title": "Category:Basketball"}],
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/basketball.jpg",
                                "user": "Pat",
                                "width": 1800,
                                "height": 1200,
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA"}
                                },
                            }
                        ],
                    }
                }
            }
        }
        with patch.object(source, "_get") as mocked_get:
            mocked_response = MagicMock()
            mocked_response.json.return_value = payload
            mocked_get.return_value = mocked_response
            results = source.search("basketball", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "wikimedia_commons")

    def test_wikimedia_source_handles_malformed_payload(self) -> None:
        source = WikimediaCommonsSource()
        with patch.object(source, "_get") as mocked_get:
            mocked_response = MagicMock()
            mocked_response.json.return_value = {"query": {"pages": []}}
            mocked_get.return_value = mocked_response

            self.assertEqual(source.search("basketball", limit=1), [])

    def test_get_retries_retryable_status_codes(self) -> None:
        source = OpenverseSource(max_retries=1, backoff_factor=0)
        retryable = MagicMock(status_code=500)
        successful = MagicMock(status_code=200)
        successful.raise_for_status.return_value = None

        with patch.object(
            source.session, "get", side_effect=[retryable, successful]
        ) as get_mock:
            with patch("src.scraper.sources.time.sleep") as sleep_mock:
                response = source._get("https://example.com")

        self.assertIs(response, successful)
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once()

    def test_get_raises_after_request_errors_exhaust_retries(self) -> None:
        source = OpenverseSource(max_retries=1, backoff_factor=0)

        with patch.object(
            source.session,
            "get",
            side_effect=requests.RequestException("boom"),
        ):
            with patch("src.scraper.sources.time.sleep"):
                with self.assertRaises(requests.RequestException):
                    source._get("https://example.com")


if __name__ == "__main__":
    unittest.main()
