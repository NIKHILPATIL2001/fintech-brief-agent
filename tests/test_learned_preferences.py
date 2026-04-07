"""Human-in-the-loop preference persistence and rank deltas."""

import json
import os
import tempfile

from fintech_brief.core.preferences import LearnedPreferences


def test_tokenize_skips_stopwords():
    lp = LearnedPreferences(":memory:")
    added = lp.learn_penalize("The Bank And A Very Long")
    assert "the" not in added
    assert "and" not in added


def test_penalize_then_rank_adjustment_negative():
    lp = LearnedPreferences(":memory:")
    lp.learn_penalize("Bitcoin NFT hype cycle continues")
    assert lp.rank_adjustment("Bitcoin ETF approved by regulator") < 0


def test_boost_then_positive_adjustment():
    lp = LearnedPreferences(":memory:")
    lp.learn_boost("Open banking API standards expand in EU")
    assert lp.rank_adjustment("New open banking partnership announced") > 0


def test_penalize_removes_conflicting_boost():
    lp = LearnedPreferences(":memory:")
    lp.learn_boost("stablecoin payments launch")
    lp.learn_penalize("stablecoin fraud probe widens")
    assert "stablecoin" in lp.penalty_terms
    assert "stablecoin" not in lp.boost_terms


def test_save_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "learned.json")
        a = LearnedPreferences(path)
        a.learn_penalize("meme stock volatility")
        b = LearnedPreferences(path)
        assert b.rank_adjustment("meme stock daily update") < 0
