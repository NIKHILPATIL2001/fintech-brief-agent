"""Protocols for dependency injection (filter ↔ storage)."""

from typing import Protocol


class StoryStore(Protocol):
    """Anything that tracks processed (title, source) pairs for deduplication."""

    def is_new_story(self, title: str, source: str) -> bool:
        """True if this pair has not been marked processed yet."""
        ...

    def mark_as_processed(self, title: str, source: str) -> None:
        """Record pair so future runs skip it."""
        ...
