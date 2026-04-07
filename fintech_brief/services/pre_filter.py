"""
Rule-based noise reduction before any LLM call.

1. Dedup via injected :class:`StoryStore` (JSON file or :memory:).
2. Noise keywords → drop.
3. Signal score gate.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fintech_brief.core.protocols import StoryStore

logger = logging.getLogger(__name__)

MIN_SIGNAL_SCORE = 5

HIGH_SIGNAL_KEYWORDS: list[str] = [
    "acquisition", "partnership", "regulatory", "launch", "funding",
    "fintech", "innovation", "digital asset", "crypto", "blockchain",
    "expansion", "ceo", "strategy", "open banking", "payment",
]

NOISE_KEYWORDS: list[str] = [
    "share price", "stock movement", "daily update", "market recap",
    "trading volume", "ohlc", "earnings preview", "conference call",
    "routine", "weekly wrap",
    "keynote", "investor day", "earnings call", "shareholder meeting",
    "annual meeting", "summit", "davos", "money 20/20",
    "market wrap", "closing bell", "premarket", "after-hours",
    "stocks rise", "stocks fall", "markets rise", "markets fall",
    "wall street", "stock market today", "s&p 500", "nasdaq composite",
]


class PreFilter:
    """Filters stories using deduplication and keyword scoring."""

    def __init__(self, store: "StoryStore") -> None:
        self.store = store

    def filter_stories(self, stories: list[dict]) -> list[dict]:
        passed: list[dict] = []
        rejected_dupe = 0
        rejected_noise = 0
        rejected_score = 0

        for s in stories:
            title_lower = s.get("title", "").lower()

            if not self.store.is_new_story(s["title"], s["source"]):
                rejected_dupe += 1
                continue

            if any(nk in title_lower for nk in NOISE_KEYWORDS):
                rejected_noise += 1
                continue

            score = sum(5 for hk in HIGH_SIGNAL_KEYWORDS if hk in title_lower)
            if score < MIN_SIGNAL_SCORE:
                rejected_score += 1
                continue

            s["pre_filter_score"] = score
            passed.append(s)

        logger.info(
            "Pre-filter: %d in → %d out  (dupe=%d, noise=%d, low-signal=%d)",
            len(stories), len(passed), rejected_dupe, rejected_noise, rejected_score,
        )
        return passed
