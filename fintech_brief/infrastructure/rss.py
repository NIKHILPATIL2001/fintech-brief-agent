"""Google News RSS fetcher — all 16 firms fetched concurrently via aiohttp."""

import asyncio
import logging
import urllib.parse
from typing import Optional

import aiohttp
import feedparser

logger = logging.getLogger(__name__)

TARGET_FIRMS: list[str] = [
    "JPMorgan Chase", "Goldman Sachs", "BlackRock", "Fidelity Investments",
    "Morgan Stanley", "Citigroup", "HSBC", "Vanguard", "State Street",
    "Barclays", "BNP Paribas", "UBS", "Stripe", "Revolut", "Visa", "Mastercard",
]

STRATEGIC_QUALIFIER = "(fintech OR acquisition OR launch OR partnership OR regulatory OR funding)"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q="

_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _fetch_firm(
    session: aiohttp.ClientSession,
    firm: str,
    hours_back: int,
) -> list[dict]:
    query = f'"{firm}" {STRATEGIC_QUALIFIER}'
    rss_url = f"{GOOGLE_NEWS_RSS}{urllib.parse.quote(query)}+when:{hours_back}h"
    try:
        async with session.get(rss_url, timeout=_FETCH_TIMEOUT) as resp:
            raw = await resp.text()
        feed = feedparser.parse(raw)
        stories = []
        for entry in getattr(feed, "entries", []):
            link = getattr(entry, "link", "")
            if not link:
                continue
            stories.append({
                "title": getattr(entry, "title", ""),
                "link": link,
                "source": getattr(getattr(entry, "source", None), "title", "Unknown"),
                "published": getattr(entry, "published", ""),
                "firm": firm,
            })
        return stories
    except Exception as e:
        logger.error("RSS fetch failed for '%s': %s", firm, e)
        return []


class NewsFetcher:
    """Fetches recent news — all target firms in parallel via asyncio.gather."""

    def __init__(self, firms: Optional[list[str]] = None) -> None:
        self.firms = firms if firms is not None else TARGET_FIRMS

    async def fetch_all_firms(self, hours_back: int = 24) -> list[dict]:
        connector = aiohttp.TCPConnector(limit=len(self.firms))
        async with aiohttp.ClientSession(connector=connector) as session:
            per_firm = await asyncio.gather(
                *[_fetch_firm(session, firm, hours_back) for firm in self.firms]
            )

        all_stories: list[dict] = []
        seen_links: set[str] = set()
        for firm_stories in per_firm:
            for s in firm_stories:
                if s["link"] not in seen_links:
                    seen_links.add(s["link"])
                    all_stories.append(s)

        logger.info("Fetched %d unique stories across %d firms", len(all_stories), len(self.firms))
        return all_stories
