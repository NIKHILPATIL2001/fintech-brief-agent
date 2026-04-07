"""Email HTML: quiet day + escaping."""

import html

import fintech_brief.services.notifier as ng


def test_build_empty_html_contains_quiet_message():
    body = ng._build_empty_html("Tuesday, April 07 2026")
    assert "No qualifying" in body
    assert "Tuesday" in body


def test_build_html_includes_executive_at_a_glance():
    stories = [
        {
            "title": "Lead acquisition story",
            "source": "Reuters",
            "link": "https://example.com/1",
            "synopsis": "Syn.",
            "impact": "HIGH",
            "category": "Strategic Move",
            "entities": ["Co"],
        },
        {
            "title": "Second",
            "source": "FT",
            "link": "https://example.com/2",
            "synopsis": "S2",
            "impact": "LOW",
            "category": "Other",
            "entities": [],
        },
    ]
    body = ng._build_html(stories, "Monday, Jan 01 2026")
    assert "This brief" in body
    assert "High" in body
    assert "Lead acquisition story" in body
    assert "Strategic Moves" in body


def test_build_html_escapes_xss_in_title():
    malicious = '<script>alert(1)</script> acquisition fintech'
    stories = [
        {
            "title": malicious,
            "source": "Reuters",
            "link": "https://example.com/x",
            "synopsis": "Safe synopsis.",
            "impact": "LOW",
            "category": "Other",
            "entities": ["Co"],
        }
    ]
    body = ng._build_html(stories, "Monday, Jan 01 2026")
    assert "<script>" not in body
    assert html.escape(malicious) in body or "&lt;script&gt;" in body
