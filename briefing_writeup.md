# FinTech Intelligence Agent — Assessment Write-Up

## What you get

A **proactive** daily pipeline that requires zero intervention. It monitors **16 global banks and asset managers** — JPMorgan, Goldman Sachs, BlackRock, Stripe, Revolut, Visa, Barclays, HSBC, and others — via Google News RSS with a `when:24h` window. Every morning at **9:00 AM**, it filters noise, enriches surviving stories with Claude, re-ranks them using multiple signals (including what you've taught it), and delivers a single, scannable HTML email.

The brief is built for a reader who has 90 seconds. The "At a Glance" strip at the top tells you how many stories, how many are HIGH impact, and the lead headline — before you read a single line of body copy. Every story below that carries a 25–40 word synopsis, source name, and a direct link to the original article. Impact level is colour-coded. Stories are grouped by strategic category. Nothing is padded.

---

## Design decisions (mapped to the brief)

| Brief requirement | Implementation |
|---|---|
| Banks & asset managers | 16-firm curated list; each firm gets its own RSS query with a strategic tail (`fintech`, `regulatory`, `acquisition`, `partnership`) so price tape never dominates |
| Daily 9 AM, last 24h | APScheduler cron at 09:00 local; `when:24h` window encoded in each RSS URL |
| Synopsis + outlet + link | Claude returns structured fields; `_merge_batch_results` in `infrastructure/llm/client.py` restores `link` and `source` from the original RSS entry so the model cannot silently drop them |
| Exclude price / conference / generic | **Pre-LLM block-list** on share price, earnings call, keynote, market tape phrases — junk never reaches the API; cost and latency both drop |

**Why pre-filter before the LLM?** Cost and failure isolation. Running Claude on 80 raw headlines per day at $0.003 per 1K tokens adds up. The pre-filter cuts that to ~20–30 stories, each one already confirmed to carry a strategic signal. It also means an Anthropic outage only affects enrichment, not whether a brief is produced at all.

**Why SMTP over Gmail OAuth?** For a daily job without a browser session, OAuth token refresh is operationally fragile — tokens expire, re-consent is manual. A Gmail App Password is a 16-character credential that works from any server or CI environment with no popup, no browser, no `credentials.json`. For production you would add a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault), but the transport remains SMTP.

**Why JSON for dedup?** SHA256(`title + source`) in a single `processed_stories.json` file. Transparent, resettable (delete the file to re-run any stories), diff-able in git. The obvious upgrade — SQLite or Postgres — is called out in `design_decisions.md`.

---

## Adaptive intelligence — how the agent gets smarter over time

This is not a static pipeline. It has a feedback layer.

**The mechanism:** when you disagree with a story the agent rated HIGH, paste its headline into the CLI or the web console:

```bash
python -m fintech_brief --penalize-title "Dogecoin rally overshadows bank earnings"
python -m fintech_brief --boost-title "EU open banking mandate accelerates API adoption"
```

`LearnedPreferences` tokenises the headline, strips stopwords, and persists meaningful terms to `learned_preferences.json`. On every future run, `ranking.py` applies bounded score adjustments: penalised terms cost up to −14 rank points per story; boosted terms add up to +10. The LLM's own `confidence` score (0.0–1.0, returned in the JSON response) adds a further ±5 points.

**Why it is auditable, not a black box:** open `learned_preferences.json` at any time and you can read every rule the system has learned, when it was added, and how many times it has fired. Delete the file to reset the agent to factory defaults. Conflicts (same word both penalised and boosted) resolve in favour of the most recent feedback.

**What it does not do yet:** implicit learning from email opens or link clicks — that would require wrapping article URLs with a redirect pixel and a small analytics store. It is the highest-priority future upgrade.

---

## Output quality — what the brief actually looks like

```
FinTech Brief | Monday, 07 April 2026
──────────────────────────────────────────────────────────────────
Strategic intelligence · 24-hour scan · 8 stories

  ● 2 High   ● 5 Medium   ● 1 Low
  Lead: JPMorgan Acquires UK Payments Startup Volt for £280M

STRATEGIC MOVES
──────────────────────────────────────────────────────────────────

  HIGH · Reuters
  JPMorgan Acquires UK Digital Payments Startup Volt for £280M

    JPMorgan Chase completed its acquisition of open-banking payments
    provider Volt, accelerating its real-time A2A payment capability
    across the European market ahead of PSD3 implementation.

    [JPMorgan Chase]  [Volt]  [Open Banking]          Read at Reuters →
```

The rendered version is in `sample_output.html`. The email is table-based HTML — no flexbox, no CSS Grid — so it renders consistently in Gmail, Outlook, and Apple Mail on desktop and mobile.

---

## Failure behaviour — in plain language

The pipeline is engineered so that **something always lands in your inbox at 9 AM**, regardless of what breaks upstream. Here is what each failure looks like to the reader and what the code does:

| What breaks | What you receive | What happens in code |
|---|---|---|
| **One RSS feed times out** | Normal brief, that firm's stories absent — no visible gap | Per-firm `try/except`; error logged; loop continues |
| **Anthropic API is down** | Full brief arrives; each story gets a rule-based synopsis instead of a Claude one | `APIError` → `_fallback_analysis()` per story |
| **Claude returns bad JSON** | Same as above — fallback applied silently | Markdown fences stripped; `JSONDecodeError` → fallback |
| **No stories survive the filter** | Short "quiet day" email — habit is never broken by silence | `send_briefing([])` sends the quiet-day template |
| **SMTP authentication fails** | No email; terminal log says exactly which credential to check | `SMTPAuthenticationError` caught with actionable message |
| **Dedup file is corrupted** | Next run starts fresh; some stories may reappear once | `JSONDecodeError` caught; warning logged; fresh store starts |

Each pipeline stage logs its result with count and timing so failures are pinpointed in logs without reading code.

---

## What I would improve next (honest, prioritised)

1. **Structured output schema** — Use Anthropic's tool-calling API to enforce JSON shape rather than relying on prompt instruction and parse recovery.
2. **Implicit feedback loop** — Redirect-pixel on article links → open/click → automatic `LearnedPreferences` update.
3. **Semantic near-duplicate detection** — Pgvector embeddings to catch paraphrased headlines that SHA256 misses.
4. **Retry with exponential backoff** — RSS timeouts and transient LLM failures currently fall through to fallback immediately; a retry layer would reduce false fallbacks.
5. **Parallel multi-model consensus** — Run Claude + GPT-4o on the same batch; send only when both agree on impact rating; reduces HIGH-impact false positives.

---

## How this maps to the evaluation rubric

| Criterion | Evidence |
|---|---|
| **Executive-readable output** | Mobile-width, impact-colour-coded, grouped by category. "At a Glance" strip states story count, high-impact count, and lead headline — a busy reader decides in 3 seconds whether to scroll. |
| **Situations the brief doesn't spell out** | Quiet-day email (habit > silence). Pre-filter extends beyond the examples (conference, generic market tape). Web console (`--ui`) for easier runs. JSON dedup is explicit and resettable. |
| **Smarter over time vs static** | Explicit feedback → auditable keyword rules → different ordering on every future run. Not a black-box model: open `learned_preferences.json` to read every rule. Documented upgrade path to implicit click-based learning. |
| **When things go wrong** | Six failure scenarios documented above in plain language. Pipeline always produces a deliverable. Each stage logs counts and timing. |
