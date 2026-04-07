"""
JSON-backed deduplication store (MVP-friendly).

SHA256(title|source) keys a small on-disk JSON file. Atomic replace on write.
Use path ``:memory:`` for tests (no file).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fintech_brief.config import PROCESSED_STORE_PATH

logger = logging.getLogger(__name__)

STORE_FORMAT_VERSION = 1


def _story_hash(title: str, source: str) -> str:
    combined = f"{title.strip().lower()}|{source.strip().lower()}"
    return hashlib.sha256(combined.encode()).hexdigest()


class JsonStoryStore:
    """
    Persists processed story fingerprints to JSON.

    File shape: ``{"version": 1, "processed": {"<sha256>": {"title", "source", "processed_at"}}}``
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path if path is not None else PROCESSED_STORE_PATH
        self._processed: dict[str, dict[str, Any]] = {}
        if self.path == ":memory:":
            return
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            proc = data.get("processed")
            if isinstance(proc, dict):
                self._processed = {str(k): v for k, v in proc.items() if isinstance(v, dict)}
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Could not load %s (%s) — starting empty store", self.path, e)

    def _save(self) -> None:
        if self.path == ":memory:":
            return
        payload = {"version": STORE_FORMAT_VERSION, "processed": self._processed}
        directory = os.path.dirname(os.path.abspath(self.path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, self.path)

    def is_new_story(self, title: str, source: str) -> bool:
        return _story_hash(title, source) not in self._processed

    def mark_as_processed(self, title: str, source: str) -> None:
        h = _story_hash(title, source)
        if h in self._processed:
            return
        self._processed[h] = {
            "title": title,
            "source": source,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
