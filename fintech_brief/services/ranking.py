"""Rank analyzed stories for the briefing (pure Python, no I/O)."""

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from fintech_brief.core.preferences import LearnedPreferences

MAX_STORIES = 10
BONUS_SOURCE = 5
BONUS_KEYWORD = 3
KEYWORD_CAP = 15

IMPACT_WEIGHTS: Dict[str, int] = {
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 1,
}

TIER_1_SOURCES: set[str] = {
    "reuters", "financial times", "bloomberg", "ft", "wall street journal",
    "wsj", "the economist", "cnbc", "business insider", "techcrunch",
}

STRATEGIC_KEYWORDS: list[str] = [
    "acquisition", "merger", "ipo", "funding", "regulation", "central bank",
    "launch", "expansion", "partnership", "ceo", "digital", "open banking",
]


def rank_stories(
    stories: list[dict],
    learned: Optional["LearnedPreferences"] = None,
) -> list[dict]:
    if learned is None:
        from fintech_brief.core.preferences import LearnedPreferences

        learned = LearnedPreferences()

    for s in stories:
        impact = s.get("impact", "LOW")
        score = IMPACT_WEIGHTS.get(impact, 1)

        source_name = s.get("source", "").lower()
        if any(t in source_name for t in TIER_1_SOURCES):
            score += BONUS_SOURCE

        title = s.get("title", "") or ""
        title_lower = title.lower()
        keyword_hits = sum(1 for kw in STRATEGIC_KEYWORDS if kw in title_lower)
        score += min(keyword_hits * BONUS_KEYWORD, KEYWORD_CAP)

        # LLM confidence (0.0–1.0) scaled to a ±5 point bonus
        confidence = float(s.get("confidence", 0.5))
        score += round((confidence - 0.5) * 10)

        adj = learned.rank_adjustment(title)
        score += adj
        s["rank_score"] = max(0, score)
        s["learned_rank_adjustment"] = adj

    ranked = sorted(stories, key=lambda x: x.get("rank_score", 0), reverse=True)
    return ranked[:MAX_STORIES]
