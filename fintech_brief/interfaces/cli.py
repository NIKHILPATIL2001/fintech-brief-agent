"""CLI entry: scheduler or one-shot run."""

import argparse
import asyncio
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from fintech_brief.infrastructure.llm.client import IntelligenceLayer
from fintech_brief.infrastructure.rss import NewsFetcher
from fintech_brief.services.pipeline import run_pipeline
from fintech_brief.services.pre_filter import PreFilter
from fintech_brief.infrastructure.storage import JsonStoryStore

load_dotenv()

_log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="FinTech Intelligence Agent")
    parser.add_argument("--now", action="store_true", help="Run pipeline immediately")
    parser.add_argument("--mock", action="store_true", help="Print HTML to stdout, do not send email")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Open local web console (http://127.0.0.1:5050) to run the pipeline",
    )
    parser.add_argument(
        "--penalize-title",
        metavar="HEADLINE",
        help="Learn from a bad headline: similar terms rank lower on future runs",
    )
    parser.add_argument(
        "--boost-title",
        metavar="HEADLINE",
        help="Learn from a good headline: similar terms rank higher on future runs",
    )
    args = parser.parse_args()

    if args.penalize_title:
        from fintech_brief.core.preferences import LearnedPreferences

        added = LearnedPreferences().learn_penalize(args.penalize_title)
        print(f"Saved penalty cues ({len(added)} new tokens): {added[:20]}")
        return

    if args.boost_title:
        from fintech_brief.core.preferences import LearnedPreferences

        added = LearnedPreferences().learn_boost(args.boost_title)
        print(f"Saved boost cues ({len(added)} new tokens): {added[:20]}")
        return

    if args.ui:
        from fintech_brief.interfaces.web.app import run_dev_server

        run_dev_server()
        return

    store = JsonStoryStore()
    fetcher = NewsFetcher()
    pre = PreFilter(store)
    intel = IntelligenceLayer()

    if args.now or args.mock:
        asyncio.run(run_pipeline(store, fetcher, pre, intel, mock=args.mock))
        return

    def daily_job() -> None:
        asyncio.run(run_pipeline(store, fetcher, pre, intel, mock=False))

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_job, "cron", hour=9, minute=0, id="daily_brief")
    log = logging.getLogger("FintechAgent")
    log.info("Scheduler started — briefing will run every day at 09:00 AM")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Agent stopped.")
