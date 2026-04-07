"""JSON dedup store persistence."""

import json
import os
import tempfile

from fintech_brief.infrastructure.storage import JsonStoryStore


def test_json_store_roundtrip_file():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "store.json")
        s = JsonStoryStore(path)
        assert s.is_new_story("A", "Reuters")
        s.mark_as_processed("A", "Reuters")
        assert not s.is_new_story("A", "Reuters")

        s2 = JsonStoryStore(path)
        assert not s2.is_new_story("A", "Reuters")


def test_corrupt_json_starts_fresh():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bad.json")
        with open(path, "w") as f:
            f.write("not json {{{")
        s = JsonStoryStore(path)
        assert s.is_new_story("X", "Y")
