"""
Versioned prompts for the intelligence layer.

Bump PROMPT_VERSION when instructions change (observable in logs).
"""

PROMPT_VERSION = "2026-04-07-v2"

SYSTEM_MESSAGE = (
    "Return ONLY a valid JSON array. No markdown, no explanation."
)

BATCH_ANALYSIS_TEMPLATE = """
You are a fintech intelligence engine.

TASK:
Analyze the following news stories and extract ONLY high-value financial insights.

STRICT FILTERING:
- IGNORE stock price movements, earnings summaries, and market commentary
- IGNORE conference announcements or generic news
- FOCUS on: acquisitions, partnerships, regulation, product launches, strategic moves

OUTPUT FORMAT (strict JSON array — one object per story, same order as input, no skipping):
[
  {{
    "title": "<copy the input title exactly>",
    "synopsis": "<25-40 words on strategic impact>",
    "impact": "HIGH | MEDIUM | LOW",
    "category": "Strategic Move | Regulatory Update | Innovation Highlight | Other",
    "entities": ["<key organisations only>"],
    "confidence": <0.0-1.0 float, how clearly important this story is>
  }}
]

RULES:
- Return exactly one object per input story, in the same order
- For low-value stories set impact LOW and confidence < 0.3 — do NOT skip them
- impact HIGH → major strategic or regulatory shift
- impact MEDIUM → meaningful product or partnership update
- impact LOW → minor or tangential update
- Keep synopsis to 25-40 words (concise = better)
- confidence = your certainty that this story matters to a fintech executive

STORIES:
{story_block}
"""


def build_batch_prompt(story_block: str) -> str:
    return BATCH_ANALYSIS_TEMPLATE.format(story_block=story_block.strip())
