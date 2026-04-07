# FinTech Intelligence Agent

> A proactive daily briefing that a busy executive would actually read —
> not a list of headlines, but a curated, scored, and continuously improving
> intelligence digest delivered to your inbox at 9 AM.

---

## What it does

Watches **16 global banks and asset managers** (JPMorgan, Goldman Sachs, BlackRock, Stripe, Revolut, Visa, Barclays, HSBC, and more) across Google News RSS. Every day at **09:00 local time** it:

1. **Fetches** all 16 firm feeds in parallel (`aiohttp` + `asyncio.gather`)
2. **Filters** noise — share prices, earnings previews, conference announcements, market recaps — before any LLM call
3. **Analyses** surviving stories with Claude (Anthropic) in concurrent batches of 5, extracting a 25–40 word synopsis, impact level, category, entities, and a confidence score
4. **Re-ranks** using source tier, strategic keyword hits, LLM confidence, and any learned preferences from your past feedback
5. **Emails** the top 10 as a clean HTML briefing — grouped by category, colour-coded by impact level — via SMTP

---

## Quick start

```bash
git clone <repo>
cd "TradingX copy"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL

pytest -q                            # 23 tests, all green
python -m fintech_brief --mock       # preview HTML in terminal (no email sent)
python -m fintech_brief --now        # run pipeline + send email now
python -m fintech_brief --ui         # web console → http://127.0.0.1:5050
python -m fintech_brief              # scheduler: runs every day at 09:00
```

**Gmail SMTP:** Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), generate a 16-char App Password, set it as `SENDER_PASSWORD` in `.env`. No OAuth, no `credentials.json`, no browser popup.

---

## Architecture

```
fintech_brief/
├── domain/
│   └── models.py                  # Story dataclass
├── infrastructure/
│   ├── rss.py                     # aiohttp async fetcher — all 16 firms in parallel
│   ├── storage.py                 # SHA256 dedup store (JSON file, atomic writes)
│   └── llm/
│       ├── client.py              # AsyncAnthropic + Semaphore(4) concurrency
│       └── prompts.py             # versioned prompt templates (PROMPT_VERSION in logs)
├── services/
│   ├── pipeline.py                # async orchestrator: fetch → filter → analyse → rank → send
│   ├── pre_filter.py              # rule-based noise removal (runs before LLM)
│   ├── ranking.py                 # multi-signal scorer: impact + source tier + keywords + confidence + learned
│   └── notifier.py                # table-based HTML email via SMTP
├── core/
│   ├── protocols.py               # StoryStore protocol (dependency injection)
│   └── preferences.py             # LearnedPreferences — adaptive re-ranking
└── interfaces/
    ├── cli.py                     # argparse entry point + APScheduler
    └── web/                       # Flask console (localhost:5050)
```

**Pipeline is fully async.** Total wall-clock time: ~10–15 s for a typical run (vs ~60 s sequential).

---

## Gets smarter over time

This is not a static pipeline. Every brief you receive is an opportunity to improve the next one.

**Flag a bad headline (noise you don't want):**
```bash
python -m fintech_brief --penalize-title "Dogecoin meme rally overshadows bank earnings"
```

**Flag a good headline (signal you want more of):**
```bash
python -m fintech_brief --boost-title "JPMorgan open banking API expansion into EU"
```

Or use the **Learn from mistakes** panel in the web console (`--ui`).

**What happens under the hood:**

The system tokenises the headline, filters stopwords, and saves meaningful terms to `learned_preferences.json`. On every future run, `ranking.py` applies bounded score adjustments: penalised terms cost up to **−14 rank points** per story; boosted terms add up to **+10**. The LLM's own `confidence` score adds a further **±5 points**.

The ruleset is fully auditable — open `learned_preferences.json` at any time to see exactly what the system has learned. Delete it to reset.

> **Current limitation:** learning is explicit (you flag stories). A future upgrade would wrap article links with a redirect to capture email opens/clicks and feed that implicit signal into `LearnedPreferences` automatically.

---

## When things go wrong

The pipeline is designed to **always send something at 9 AM.** Here is what happens in every failure scenario:

| What breaks | What the user experiences | How it's handled in code |
|---|---|---|
| **One RSS feed times out** | 15 other firms still run. No visible gap. | Per-firm `try/except` in `rss.py`; error logged, loop continues |
| **Anthropic API is down** | Email still arrives. Each story gets a rule-based synopsis instead of a Claude one. | `APIError` caught in `client.py` → `_fallback_analysis()` applied per story |
| **Claude returns malformed JSON** | Same as above — fallback kicks in silently. | Markdown fences stripped; `JSONDecodeError` caught; fallback applied |
| **No stories survive the filter** | A short "quiet day" email arrives. The 9 AM habit is never broken by silence. | `send_briefing([])` in `pipeline.py` sends the quiet-day template |
| **SMTP authentication fails** | No email sent. Clear error logged: `SMTP auth failed — check SENDER_EMAIL / SENDER_PASSWORD`. | `SMTPAuthenticationError` caught separately with actionable message |
| **Dedup file is corrupted** | Next run starts with a fresh empty store. Stories seen before may reappear once. | `json.JSONDecodeError` caught in `storage._load()`; warning logged; `_processed = {}` |
| **LLM drops `link` or `source` fields** | Original article link and outlet name are preserved in the email. | `_merge_batch_results` restores original dict values after LLM merge |

Each pipeline stage logs its result (`[Fetch]`, `[Pre-Filter]`, `[Intel]`, `[Rank]`, `[Send]`) with counts and timing so failures are immediately locatable in logs.

---

## What the output looks like

The email is table-based HTML (Gmail-safe, mobile-responsive). Each story shows:

```
High Impact · Reuters
JPMorgan Acquires UK Digital Payments Startup Volt for $300M

  JPMorgan Chase completed its acquisition of London-based open-banking
  payments provider Volt, signalling a strategic push into real-time
  account-to-account payments across Europe.

  [JPMORGAN CHASE]  [VOLT]                              Read →
```

Stories are grouped by **Strategic Moves / Regulatory Updates / Innovation**. The summary strip at the top shows impact distribution (● High ● Medium ● Low) and the lead headline so the reader knows in 3 seconds whether to open the email.

See `sample_output.html` for a rendered example.

---

## Key environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `SENDER_EMAIL` | Yes | Gmail address used to send |
| `SENDER_PASSWORD` | Yes | Gmail App Password (16 chars) |
| `RECIPIENT_EMAIL` | Yes | Where the brief is delivered |
| `ANTHROPIC_MODEL` | No | Defaults to `claude-sonnet-4-20250514` |
| `LOG_LEVEL` | No | Defaults to `INFO` |
| `PROCESSED_STORE_PATH` | No | Dedup store path (default: `processed_stories.json`) |
| `FB_WEB_PORT` | No | Web console port (default: `5050`) |

---

## Tests

```bash
pytest -q   # 23 tests, ~0.3s
```

Covers: LLM JSON parsing and merge, HTML rendering and XSS escaping, pre-filter (noise, dedup, signal gate), ranking (ordering, caps, learned preferences), dedup store (roundtrip, corrupt-file recovery), learned preferences (tokenisation, penalty/boost, persistence), web console routes.

---

## Deliverables

| File | What it is |
|---|---|
| `fintech_brief/` | Full source package |
| `tests/` | 23 unit tests |
| `sample_output.html` | Rendered email example |
| `briefing_writeup.md` | Design decisions and trade-offs |
| `design_decisions.md` | Extended architecture rationale |
| `.env.example` | Environment variable template |
