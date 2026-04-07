"""Claude (Anthropic) batch analysis — batches run concurrently, rate-limited by Semaphore."""

import asyncio
import json
import logging
import os
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv

from fintech_brief.infrastructure.llm.prompts import PROMPT_VERSION, SYSTEM_MESSAGE, build_batch_prompt

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Max concurrent LLM calls — prevents rate-limit errors while keeping throughput high.
_MAX_CONCURRENT_LLM = 4


def _parse_json_list(raw_text: str) -> Any:
    t = raw_text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        t = "\n".join(lines).strip()
    return json.loads(t)


class IntelligenceLayer:
    """LLM reasoning and synopsis generation — async, rate-limited."""

    def __init__(self) -> None:
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._model: Optional[str] = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
            self._model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
            logger.info("Intelligence: Anthropic async (%s)", self._model)
        else:
            logger.warning("No ANTHROPIC_API_KEY. Operating in fallback (rule-based) mode.")

    async def analyze_batch(self, stories: list[dict], sem: asyncio.Semaphore) -> list[dict]:
        """Analyze one batch, holding the semaphore to cap concurrency."""
        if not self._client or not stories:
            return [self._fallback_analysis(s) for s in stories]

        async with sem:
            formatted = "\n---\n".join(
                f"TITLE: {s['title']}\nSOURCE: {s['source']}\nFIRM: {s['firm']}"
                for s in stories
            )
            prompt = build_batch_prompt(formatted)
            logger.info(
                "LLM batch: model=%s prompt_version=%s stories=%d chars=%d",
                self._model, PROMPT_VERSION, len(stories), len(prompt),
            )

            raw_text: Optional[str] = None
            try:
                assert self._client is not None and self._model is not None
                msg = await self._client.messages.create(
                    model=self._model,
                    max_tokens=8192,
                    system=SYSTEM_MESSAGE,
                    messages=[{"role": "user", "content": prompt.strip()}],
                )
                parts = [block.text for block in msg.content if hasattr(block, "text")]
                raw_text = "".join(parts).strip()
                if not raw_text:
                    logger.error("Empty Anthropic response.")
                    return [self._fallback_analysis(s) for s in stories]
                data = _parse_json_list(raw_text)
                return self._merge_batch_results(data, stories)
            except json.JSONDecodeError as e:
                logger.error("JSONDecodeError on Anthropic output: %s", e)
                logger.debug("Raw LLM output: %s", raw_text)
                return [self._fallback_analysis(s) for s in stories]
            except anthropic.APIError as e:
                logger.error("Anthropic API failed: %s", e)
                return [self._fallback_analysis(s) for s in stories]
            except Exception as e:
                logger.exception("Unexpected error in IntelligenceLayer: %s", e)
                return [self._fallback_analysis(s) for s in stories]

    async def analyze_all(self, batches: list[list[dict]]) -> list[dict]:
        """Fire all batches concurrently, capped at _MAX_CONCURRENT_LLM simultaneous calls."""
        sem = asyncio.Semaphore(_MAX_CONCURRENT_LLM)
        results = await asyncio.gather(
            *[self.analyze_batch(batch, sem) for batch in batches]
        )
        return [story for batch_result in results for story in batch_result]

    @staticmethod
    def _merge_batch_results(data: Any, stories: list[dict]) -> list[dict]:
        if not isinstance(data, list):
            logger.error("LLM returned JSON that is not a list: %s", type(data).__name__)
            return [IntelligenceLayer._fallback_analysis(s) for s in stories]
        results: list[dict] = []
        for i, s in enumerate(stories):
            item = data[i] if i < len(data) else None
            if isinstance(item, dict):
                merged = s.copy()
                merged.update(item)
                for key in ("link", "source", "firm", "published"):
                    if not merged.get(key) and s.get(key):
                        merged[key] = s[key]
                results.append(merged)
            else:
                results.append(IntelligenceLayer._fallback_analysis(s))
        return results

    @staticmethod
    def _fallback_analysis(s: dict) -> dict:
        return {
            **s,
            "synopsis": f"Strategic update involving {s.get('firm', 'this firm')}. See link for details.",
            "impact": "MEDIUM",
            "category": "Strategic Move",
            "entities": [s.get("firm", "")],
        }
