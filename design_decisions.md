# FinTech Intelligence Agent — Design & Architecture Write-Up

---

## Key Features Implemented

| Feature | Detail |
|---|---|
| **Proactive daily briefing** | APScheduler fires at 09:00 — zero manual prompts required |
| **16 target firms** | JPMorgan, Goldman, BlackRock, Stripe, Revolut, Visa, etc. via Google News RSS |
| **Pre-LLM noise filter** | Rule-based keyword scoring before any API call — cuts cost and latency |
| **Concurrent LLM batching** | Batches of 5 stories, up to 4 concurrent Anthropic calls via `asyncio.Semaphore` |
| **Structured enrichment** | Claude adds `synopsis`, `impact` (HIGH/MED/LOW), `category`, `entities` per story |
| **Smart deduplication** | SHA256(`title + source`) persisted in `processed_stories.json` across runs |
| **Learned re-ranking** | User flags good/bad headlines → tokenised keywords stored → applied to future runs |
| **HTML email output** | Mobile-width, colour-coded by impact, grouped by category, "at a glance" header |
| **Web UI console** | Flask on `:5050` — trigger runs, view output, submit feedback without the CLI |
| **Quiet-day handling** | Empty brief still sends so the 9 AM habit is never broken by silence |

---

## Decisions Made

### 1. Google News RSS over a paid news API
Free, zero-key, well-structured per-firm queries with a `when:24h` window. The trade-off is occasional duplicate headlines across firms (handled by SHA256 dedup) and no full article body (handled by Claude summarising the title + source context). Alternatives considered: **Perplexity API** (good summaries but charges per query and adds a round-trip latency; better suited to on-demand Q&A than batch ingestion), **NewsAPI** (free tier limits hits per day — breaks for 16 firms × multiple queries).

### 2. Anthropic Claude over GPT-4o / Gemini / parallel multi-model
Claude was chosen for its strong structured-output reliability and long context window. The batch prompt asks for a strict JSON list — Claude honours this format more consistently than GPT-3.5 and is cheaper than GPT-4o at comparable quality. **Parallel AI (running multiple LLMs simultaneously and merging answers)** would improve confidence but multiplies cost and complexity; it is the right upgrade for a production signal layer where accuracy > cost.

### 3. Pre-filter before the LLM (not after)
Most raw RSS headlines are price-movement noise, conference announcements, or generic market recaps. Dropping them before the API call means Claude only sees strategically relevant titles — cheaper, faster, and it avoids the model returning low-quality synopses for junk input. The filter runs in three passes: dedup → noise keyword block-list → minimum signal score.

### 4. `asyncio` + `asyncio.Semaphore` for concurrency
All 16 firms are fetched concurrently (`aiohttp`). LLM batches run concurrently capped at 4 simultaneous calls to respect Anthropic's rate limits without adding an external queue. This keeps total pipeline time under ~30 s for a typical run with no extra infrastructure.

### 5. JSON file for dedup and preferences (not a database)
For a single-process daily job, a JSON file is transparent, resettable, and version-control friendly. The dedup key is a SHA256 hash so the file stays compact even after months of runs. SQLite is the obvious upgrade if multiple processes write, or if the store needs indexed queries.

### 6. Flask subprocess model for the web UI
The web layer never imports the pipeline in-process. It spawns `python -m fintech_brief --now` as a subprocess so the web server and the pipeline run in isolated processes. This avoids blocking the event loop and means the UI always mirrors exactly what the CLI does — no divergence risk.

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| **Anthropic down / rate-limited** | `APIError` caught per batch → `_fallback_analysis()` generates a rule-based synopsis; run completes |
| **Malformed LLM JSON** | `JSONDecodeError` caught; markdown fences stripped; fallback applied |
| **LLM returns fewer items than batch size** | `_merge_batch_results` maps by index, fills gaps with fallback |
| **One RSS firm feed fails** | Per-firm `try/continue` — other 15 firms still run |
| **No stories survive pre-filter** | `send_briefing([])` sends a short "quiet day" email — no silent failure |
| **Corrupt dedup JSON** | `_load` catches `json.JSONDecodeError` → logs warning → starts fresh empty store |
| **LLM drops `link` / `source` fields** | `_merge_batch_results` restores them from the original dict after merge |
| **Duplicate story across multiple firms** | SHA256 dedup catches same title/source across firm feeds in the same run |

---

## What I Would Improve With More Time

1. **Structured output schema enforcement** — Use Anthropic's tool-calling / response format API to guarantee JSON shape rather than relying on prompt instruction and parse recovery.
2. **SQLite / Postgres dedup store** — Replace the JSON file with a proper DB for concurrent writers, indexed queries, and TTL-based expiry of old hashes.
3. **Semantic near-duplicate detection** — Pgvector embeddings to catch paraphrased headlines that SHA256 misses.
4. **Implicit feedback loop** — Wrap article links with a redirect pixel to capture opens/clicks and feed that signal into `LearnedPreferences` automatically (currently requires explicit CLI/UI flags).
5. **Parallel multi-model consensus** — Run Claude + GPT-4o in parallel on the same batch, compare impact ratings, and only send to the user when both agree — dramatically reduces hallucinated HIGH-impact classifications.
6. **Perplexity / web-grounded summaries** — For HIGH-impact stories, hit Perplexity's online API to ground the synopsis in real-time web context rather than just the RSS title.
7. **Retry + exponential backoff** — RSS timeouts and LLM transient failures currently fall through to fallback immediately; a retry layer with jitter would reduce false fallbacks.
8. **Secret rotation docs + CI pipeline** — Production deployment needs documented key rotation for `ANTHROPIC_API_KEY` and SMTP credentials, plus a GitHub Actions workflow for tests on every push.

---

## Why This Stack vs Alternatives

| Tool chosen | Why | What we gave up |
|---|---|---|
| **Google News RSS** | Free, no key, `when:24h` window | No full article body; occasional dupes |
| **Anthropic Claude** | Best structured-JSON compliance, long context | Slightly higher cost than GPT-3.5; single vendor |
| **aiohttp + asyncio** | Native async; no thread overhead; fast concurrent fetches | Steeper debugging vs `requests` |
| **APScheduler** | Zero-infra cron; runs in-process | Not suitable for distributed / multi-instance deploys |
| **Flask** | Minimal footprint for a local dev console | Not production-grade (use FastAPI + ASGI for prod) |
| **JSON store** | Transparent, resettable, zero infra | No concurrent writes, no indexed queries |

**Not used — and why:**

- **Perplexity API** — Great for on-demand Q&A; too expensive and latency-heavy for bulk batch enrichment of 30–50 stories daily. Best reserved for a "deep-dive" mode on a single HIGH-impact story.
- **Parallel AI (multi-model ensemble)** — Doubles/triples LLM cost. The right trade-off for production accuracy but out of scope for an MVP budget.
- **LangChain / LlamaIndex** — Added abstraction with no concrete benefit here; the pipeline stages are simple enough to wire directly, and the framework overhead complicates debugging.
- **Kafka / Redis queue** — Overkill for a single daily job; correct choice if this becomes a real-time stream or multi-tenant service.
