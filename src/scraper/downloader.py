from __future__ import annotations

import re
from pathlib import Path

import requests

from src.scraper.sources import SourceCandidate


class Downloader:
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "basketball-photo-analyzer/0.1 (+https://github.com/nickth3man/basketball-photos)"
            }
        )

    def download(self, candidate: SourceCandidate, target_dir: str | Path) -> Path:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        response = self.session.get(candidate.image_url, timeout=self.timeout)
        response.raise_for_status()
        content_type = (
            response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        )
        if content_type not in self.allowed_content_types:
            raise ValueError(f"Unsupported content type: {content_type}")

        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[content_type]
        slug = (
            re.sub(r"[^a-z0-9]+", "-", candidate.title.lower()).strip("-")
            or "candidate"
        )
        file_path = target_dir / f"{slug[:60]}-{candidate.source}{extension}"
        file_path.write_bytes(response.content)
        return file_path
