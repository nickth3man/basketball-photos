from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.scraper.sources import OpenverseSource, WikimediaCommonsSource


class DiscoverySourcesTest(unittest.TestCase):
    def test_openverse_source_maps_results(self) -> None:
        # TODO: Add mocked HTTP failure and malformed payload cases so these
        # API adapters prove their behavior outside the happy path.
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


if __name__ == "__main__":
    unittest.main()
