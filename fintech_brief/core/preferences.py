"""
Human-in-the-loop preferences persisted to JSON.

Not a black-box model: you flag bad or good headlines; we tokenize titles and
store terms that **raise or lower** rank scores on future runs. Fully auditable
in ``learned_preferences.json``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PATH = os.environ.get("LEARNED_PREFS_PATH", "learned_preferences.json")

# Cap how much learned rules can move a single story (keeps ranking stable).
MAX_PENALTY_PER_STORY = 14
MAX_BOOST_PER_STORY = 10
POINTS_PER_PENALTY_HIT = 4
POINTS_PER_BOOST_HIT = 3

MAX_PENALTY_TERMS = 100
MAX_BOOST_TERMS = 60
MAX_LOG_ENTRIES = 80

FORMAT_VERSION = 1

_STOPWORDS = frozenset(
    """
    the and for not with from that this was are but has had his her its one our out
    all any can may new per sub inc llc ltd plc corp company bank banks says said
    say also into over such than then them these they were what when will with
    your more most some very much about after before being both each few get got
    how its just like make many now see two who way use org com www
    """.split()
)


def _tokens(title: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z]{3,}", title.lower())
    out: list[str] = []
    for w in raw:
        if w in _STOPWORDS or len(w) > 24:
            continue
        out.append(w)
    return out


class LearnedPreferences:
    """Load/save penalty & boost term lists; apply bounded rank deltas."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path if path is not None else DEFAULT_PATH
        self.penalty_terms: list[str] = []
        self.boost_terms: list[str] = []
        self._log: list[dict[str, Any]] = []
        if self.path == ":memory:":
            return
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("penalty_terms")
            b = data.get("boost_terms")
            if isinstance(p, list):
                self.penalty_terms = [str(x).lower() for x in p if isinstance(x, str) and x.strip()]
            if isinstance(b, list):
                self.boost_terms = [str(x).lower() for x in b if isinstance(x, str) and x.strip()]
            lg = data.get("log")
            if isinstance(lg, list):
                self._log = [x for x in lg if isinstance(x, dict)][-MAX_LOG_ENTRIES:]
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Could not load %s (%s) — using empty preferences", self.path, e)

    def save(self) -> None:
        if self.path == ":memory:":
            return
        payload = {
            "version": FORMAT_VERSION,
            "penalty_terms": self.penalty_terms,
            "boost_terms": self.boost_terms,
            "log": self._log[-MAX_LOG_ENTRIES:],
        }
        directory = os.path.dirname(os.path.abspath(self.path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, self.path)

    def _append_log(self, action: str, title: str) -> None:
        sample = title.strip()[:200]
        self._log.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "title_sample": sample,
            }
        )
        self._log = self._log[-MAX_LOG_ENTRIES:]

    def _dedupe_ordered(self, terms: list[str], cap: int) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for t in terms:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out[-cap:] if len(out) > cap else out

    def learn_penalize(self, title: str) -> list[str]:
        """Extract terms from a headline you consider a mistake; future titles containing them rank lower."""
        added: list[str] = []
        for tok in _tokens(title):
            if tok in self.boost_terms:
                self.boost_terms = [x for x in self.boost_terms if x != tok]
            if tok not in self.penalty_terms:
                self.penalty_terms.append(tok)
                added.append(tok)
        self.penalty_terms = self._dedupe_ordered(self.penalty_terms, MAX_PENALTY_TERMS)
        self._append_log("penalize", title)
        self.save()
        logger.info("Learned penalize terms from headline: %s", added[:12])
        return added

    def learn_boost(self, title: str) -> list[str]:
        """Extract terms from a headline you want more of; similar future lines rank higher."""
        added: list[str] = []
        for tok in _tokens(title):
            if tok in self.penalty_terms:
                self.penalty_terms = [x for x in self.penalty_terms if x != tok]
            if tok not in self.boost_terms:
                self.boost_terms.append(tok)
                added.append(tok)
        self.boost_terms = self._dedupe_ordered(self.boost_terms, MAX_BOOST_TERMS)
        self._append_log("boost", title)
        self.save()
        logger.info("Learned boost terms from headline: %s", added[:12])
        return added

    def rank_adjustment(self, title: str) -> int:
        """Bounded integer added to base rank_score (can be negative)."""
        t = title.lower()
        pen = sum(POINTS_PER_PENALTY_HIT for term in self.penalty_terms if term in t)
        boost = sum(POINTS_PER_BOOST_HIT for term in self.boost_terms if term in t)
        pen = min(pen, MAX_PENALTY_PER_STORY)
        boost = min(boost, MAX_BOOST_PER_STORY)
        return boost - pen

    def summary(self) -> dict[str, Any]:
        return {
            "penalty_term_count": len(self.penalty_terms),
            "boost_term_count": len(self.boost_terms),
            "recent_log": list(reversed(self._log[-8:])),
        }
