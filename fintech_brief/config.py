"""Paths and defaults (overridable via environment)."""

import os

# Dedup state file (MVP). Use ``:memory:`` in tests only.
PROCESSED_STORE_PATH: str = os.environ.get("PROCESSED_STORE_PATH", "processed_stories.json")
