from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests import RequestException

from src.scraper.http import DEFAULT_USER_AGENT, build_http_session

logger = logging.getLogger(__name__)


@dataclass
class SourceCandidate:
    source: str
    title: str
    image_url: str
    page_url: str
    license: str
    creator: str
    width: int | None = None
    height: int | None = None
    tags: list[str] | None = None

    def context_text(self) -> str:
        tokens = [self.title, self.creator, self.license, *(self.tags or [])]
        return " ".join(token for token in tokens if token)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "image_url": self.image_url,
            "page_url": self.page_url,
            "license": self.license,
            "creator": self.creator,
            "width": self.width,
            "height": self.height,
            "tags": self.tags or [],
        }


class BaseSource:
    user_agent = DEFAULT_USER_AGENT
    retry_status_codes = {429, 500, 502, 503, 504}

    def __init__(
        self, timeout: int = 20, max_retries: int = 2, backoff_factor: float = 0.5
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = build_http_session(self.user_agent)

    def _get(
        self, url: str, *, params: dict[str, Any] | None = None
    ) -> requests.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if (
                    response.status_code in self.retry_status_codes
                    and attempt < self.max_retries
                ):
                    time.sleep(self.backoff_factor * (2**attempt))
                    continue
                response.raise_for_status()
                return response
            except RequestException:
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.backoff_factor * (2**attempt))

        raise RuntimeError("Unreachable retry loop exit")


class OpenverseSource(BaseSource):
    endpoint = "https://api.openverse.org/v1/images/"

    def search(self, query: str, limit: int = 10) -> list[SourceCandidate]:
        params = {
            "q": query,
            "page_size": limit,
            "license_type": "commercial",
            "category": "photograph",
        }
        payload = self._get(self.endpoint, params=params).json()
        if not isinstance(payload, dict):
            return []
        results: list[SourceCandidate] = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            image_url = item.get("url") or item.get("thumbnail")
            if not image_url:
                continue
            results.append(
                SourceCandidate(
                    source="openverse",
                    title=item.get("title") or query,
                    image_url=image_url,
                    page_url=item.get("foreign_landing_url") or image_url,
                    license=(item.get("license") or "unknown").lower(),
                    creator=item.get("creator") or "unknown",
                    width=item.get("width"),
                    height=item.get("height"),
                    tags=[
                        tag.get("name", "")
                        for tag in item.get("tags", [])
                        if tag.get("name")
                    ],
                )
            )
        return results


class WikimediaCommonsSource(BaseSource):
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def search(self, query: str, limit: int = 10) -> list[SourceCandidate]:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo|info|categories",
            "iiprop": "url|user|size|extmetadata",
            "inprop": "url",
            "cllimit": "max",
            "format": "json",
        }
        payload = self._get(self.endpoint, params=params).json()
        if not isinstance(payload, dict):
            return []
        pages = payload.get("query", {}).get("pages", {})
        if not isinstance(pages, dict):
            return []
        results: list[SourceCandidate] = []
        for page in pages.values():
            if not isinstance(page, dict):
                continue
            image_info = (page.get("imageinfo") or [{}])[0]
            image_url = image_info.get("url")
            if not image_url:
                continue
            categories = [
                entry.get("title", "") for entry in page.get("categories", [])
            ]
            extmetadata = image_info.get("extmetadata") or {}
            license_value = extmetadata.get("LicenseShortName", {}).get(
                "value", "unknown"
            )
            creator = extmetadata.get("Artist", {}).get(
                "value", image_info.get("user", "unknown")
            )
            results.append(
                SourceCandidate(
                    source="wikimedia_commons",
                    title=page.get("title", query),
                    image_url=image_url,
                    page_url=page.get("fullurl") or image_url,
                    license=str(license_value).lower(),
                    creator=str(creator),
                    width=image_info.get("width"),
                    height=image_info.get("height"),
                    tags=categories,
                )
            )
        return results
