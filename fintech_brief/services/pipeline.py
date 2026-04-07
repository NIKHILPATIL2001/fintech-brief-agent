"""End-to-end async run: fetch → filter → LLM (concurrent) → rank → notify."""

import asyncio
import logging
from datetime import datetime

from fintech_brief.infrastructure.llm.client import IntelligenceLayer
from fintech_brief.core.preferences import LearnedPreferences
from fintech_brief.infrastructure.rss import NewsFetcher
from fintech_brief.services.notifier import send_briefing
from fintech_brief.services.pre_filter import PreFilter
from fintech_brief.services.ranking import rank_stories
from fintech_brief.infrastructure.storage import JsonStoryStore

logger = logging.getLogger("FintechAgent")

BATCH_SIZE = 5


async def run_pipeline(
    store: JsonStoryStore,
    fetcher: NewsFetcher,
    pre_filter: PreFilter,
    intel: IntelligenceLayer,
    *,
    learned: LearnedPreferences | None = None,
    mock: bool = False,
) -> None:
    start = datetime.now()
    prefs = learned if learned is not None else LearnedPreferences()
    logger.info("=" * 50)
    logger.info("Pipeline started")

    # Fetch all 16 firms concurrently
    raw = await fetcher.fetch_all_firms(hours_back=24)
    logger.info("[Fetch]      %d raw stories pulled", len(raw))

    filtered = pre_filter.filter_stories(raw)
    logger.info("[Pre-Filter] %d stories passed (noise/dupes removed)", len(filtered))

    if not filtered:
        logger.warning("No stories survived pre-filter. Sending quiet-day briefing.")
        success = send_briefing([], mock=mock)
        elapsed = (datetime.now() - start).seconds
        logger.info("[Send]       %s  (quiet day, %ds)", "OK ✓" if success else "FAILED ✗", elapsed)
        logger.info("=" * 50)
        return

    # Split into batches and run all batches concurrently (rate-limited)
    batches = [filtered[i : i + BATCH_SIZE] for i in range(0, len(filtered), BATCH_SIZE)]
    analysed = await intel.analyze_all(batches)
    logger.info("[Intel]      %d stories analysed by Claude (%d batches, ≤4 concurrent)", len(analysed), len(batches))

    for s in analysed:
        store.mark_as_processed(s["title"], s["source"])

    top_stories = rank_stories(analysed, learned=prefs)
    adjusted = sum(1 for s in analysed if s.get("learned_rank_adjustment", 0) != 0)
    if adjusted:
        logger.info("[Learn]      Applied learned rank tweaks to %d stories this run", adjusted)
    logger.info("[Rank]       Top %d stories selected for briefing", len(top_stories))

    success = send_briefing(top_stories, mock=mock)
    elapsed = (datetime.now() - start).seconds
    logger.info("[Send]       %s  (%ds total)", "OK ✓" if success else "FAILED ✗", elapsed)
    logger.info("=" * 50)
