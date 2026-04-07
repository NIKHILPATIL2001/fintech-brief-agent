"""Web console: static routes only (no full pipeline in CI)."""

from fintech_brief.interfaces.web.app import create_app


def test_index_renders():
    c = create_app().test_client()
    r = c.get("/")
    assert r.status_code == 200
    assert b"Briefing console" in r.data


def test_status_idle():
    c = create_app().test_client()
    r = c.get("/api/status")
    assert r.status_code == 200
    j = r.get_json()
    assert j["running"] is False
    assert j["last"] is None


def test_learn_summary_ok():
    r = create_app().test_client().get("/api/learn/summary")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "penalty_term_count" in j
