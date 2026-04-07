"""LLM JSON parsing and merge (no API)."""

import json

import fintech_brief.infrastructure.llm.client as il


def test_parse_json_list_plain_array():
    data = [{"title": "A", "synopsis": "S", "impact": "LOW", "category": "Other", "entities": []}]
    raw = json.dumps(data)
    assert il._parse_json_list(raw) == data


def test_parse_json_list_strips_markdown_fence():
    inner = [{"title": "A", "synopsis": "S", "impact": "MEDIUM", "category": "Other", "entities": ["E"]}]
    raw = "```json\n" + json.dumps(inner) + "\n```"
    assert il._parse_json_list(raw) == inner


def test_merge_preserves_link():
    stories = [{"title": "T", "source": "Reuters", "firm": "F", "link": "https://example.com/a"}]
    data = [{"title": "T", "synopsis": "Syn", "impact": "LOW", "category": "Other", "entities": []}]
    merged = il.IntelligenceLayer._merge_batch_results(data, stories)
    assert merged[0]["link"] == "https://example.com/a"
