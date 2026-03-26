from __future__ import annotations

import requests

DEFAULT_USER_AGENT = (
    "basketball-photo-analyzer/0.1 (+https://github.com/nickth3man/basketball-photos)"
)


def build_http_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session
