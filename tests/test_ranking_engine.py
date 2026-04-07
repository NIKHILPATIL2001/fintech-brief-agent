"""Ranking: ordering, caps, impact weights, learned preferences."""

from fintech_brief.core.preferences import LearnedPreferences
import fintech_brief.services.ranking as re


def _mem() -> LearnedPreferences:
    return LearnedPreferences(":memory:")


def test_rank_stories_orders_by_score_high_first():
    stories = [
        {"title": "Low story", "source": "Blog", "impact": "LOW"},
        {"title": "Goldman IPO expansion", "source": "Reuters", "impact": "HIGH"},
    ]
    out = re.rank_stories(stories, learned=_mem())
    assert out[0]["title"] == "Goldman IPO expansion"
    assert out[0].get("rank_score", 0) >= out[1].get("rank_score", 0)


def test_rank_stories_respects_max_stories():
    stories = [
        {"title": f"Story {i} acquisition", "source": "Reuters", "impact": "HIGH"}
        for i in range(15)
    ]
    out = re.rank_stories(stories, learned=_mem())
    assert len(out) == re.MAX_STORIES


def test_unknown_impact_defaults_to_low_weight():
    s = [{"title": "Odd", "source": "X", "impact": "WEIRD"}]
    re.rank_stories(s, learned=_mem())
    assert s[0]["rank_score"] == re.IMPACT_WEIGHTS.get("WEIRD", 1)


def test_learned_penalty_can_reorder():
    base = _mem()
    penalized = LearnedPreferences(":memory:")
    penalized.penalty_terms = ["dogecoin"]

    a = {"title": "Major bank open banking deal", "source": "Reuters", "impact": "HIGH"}
    b = {"title": "Dogecoin rally hits new meme high", "source": "Reuters", "impact": "HIGH"}
    stories = [a, b]
    out_base = re.rank_stories([dict(x) for x in stories], learned=base)
    out_pen = re.rank_stories([dict(x) for x in stories], learned=penalized)
    assert out_pen[0]["title"] == "Major bank open banking deal"
    assert any(s.get("learned_rank_adjustment", 0) < 0 for s in out_pen if "dogecoin" in s["title"].lower())
