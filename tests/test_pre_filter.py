"""Pre-filter: dedup store, noise, signal gate."""

from fintech_brief.services.pre_filter import PreFilter
from fintech_brief.infrastructure.storage import JsonStoryStore


def test_noise_share_price_rejected():
    store = JsonStoryStore(":memory:")
    pf = PreFilter(store)
    raw = [{"title": "Bank share price jumps 3%", "source": "Yahoo", "firm": "X"}]
    assert pf.filter_stories(raw) == []


def test_strategic_story_passes():
    store = JsonStoryStore(":memory:")
    pf = PreFilter(store)
    raw = [
        {
            "title": "JPMorgan announces fintech acquisition in open banking",
            "source": "Reuters",
            "firm": "JPMorgan",
        }
    ]
    out = pf.filter_stories(raw)
    assert len(out) == 1
    assert "pre_filter_score" in out[0]


def test_duplicate_skipped_after_marked_processed():
    store = JsonStoryStore(":memory:")
    pf = PreFilter(store)
    story = {
        "title": "Same headline acquisition fintech",
        "source": "FT",
        "firm": "GS",
    }
    assert len(pf.filter_stories([dict(story)])) == 1
    store.mark_as_processed(story["title"], story["source"])
    assert pf.filter_stories([dict(story)]) == []
