from __future__ import annotations

import re
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.scraper.http import build_http_session
from src.scraper.sources import SourceCandidate


class Downloader:
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}
    content_type_extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = build_http_session()

    def download(self, candidate: SourceCandidate, target_dir: str | Path) -> Path:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        response = self.session.get(
            candidate.image_url, timeout=self.timeout, stream=True
        )
        response.raise_for_status()

        content_type = (
            response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        )
        if content_type not in self.allowed_content_types:
            raise ValueError(f"Unsupported content type: {content_type}")

        extension = self.content_type_extensions[content_type]
        file_path = self._build_destination_path(candidate, target_dir, extension)

        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=target_dir, suffix=extension
        ) as temp_file:
            temp_path = Path(temp_file.name)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

        try:
            self._verify_downloaded_image(temp_path)
            temp_path.replace(file_path)
            return file_path
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _build_destination_path(
        self, candidate: SourceCandidate, target_dir: Path, extension: str
    ) -> Path:
        slug = (
            re.sub(r"[^a-z0-9]+", "-", candidate.title.lower()).strip("-")
            or "candidate"
        )
        base_name = f"{slug[:60]}-{candidate.source}"
        candidate_path = target_dir / f"{base_name}{extension}"
        suffix = 2

        while candidate_path.exists():
            candidate_path = target_dir / f"{base_name}-{suffix}{extension}"
            suffix += 1

        return candidate_path

    def _verify_downloaded_image(self, file_path: Path) -> None:
        try:
            with Image.open(file_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError(
                f"Downloaded file is not a valid image: {file_path}"
            ) from error
