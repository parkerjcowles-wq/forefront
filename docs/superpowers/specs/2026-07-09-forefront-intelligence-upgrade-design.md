# Forefront — Intelligence Upgrade (Design)

**Date:** 2026-07-09
**Status:** Approved design, pending implementation plan
**Approach:** A — evolve the existing single Groq-call pipeline (chosen over a
multi-call structured pipeline and a section-plugin rewrite).

## Goal

Turn Forefront from a supply-chain-only, single-field brief generator into a
configurable pre-call **sales intelligence** tool: the rep names a company,
optionally names the department/focus they're selling into, gives one line of
call context, and optionally names the product they're pushing — and gets a
tighter, richer, sourced brief that now includes a financial read and deal
framing. Same free Exa + Groq engine, same live-demoable resume artifact, no new
API keys.

## Current state (baseline)

- **Backend:** FastAPI. `exa_search(company)` runs 4 hardcoded supply-chain
  queries **sequentially** (12s timeout each). `generate_brief(company)` feeds
  the excerpts to one Groq `llama-3.3-70b-versatile` call using a fixed
  six-section supply-chain system prompt. `SECTIONS` is a hardcoded list the
  frontend and tests depend on.
- **Frontend:** editorial single page — large masthead + oversized Playfair
  headline + lede, then a single company input, sample chips, and the rendered
  brief. Markdown rendered via marked.js + DOMPurify (fail-closed).
- **Abuse control:** cookie-based per-session cap (`MAX_CUSTOM_BRIEFS=3`) + 24h
  in-process cache. No security headers, no per-IP limit, docs endpoints open.
- **Tests:** 27 passing, Exa + Groq fully mocked.

## Scope

### 1. Input model

Replace the single company field with a compact form:

| Field | Required | Notes |
|---|---|---|
| Company | Yes | Existing sanitized field. |
| Focus / department | No | Free text, e.g. "marketing", "procurement", "IT". Blank = default supply-chain/ops lens. |
| Call context | No | One line — what the call is about. Shapes Talking Points. |
| Product you're pitching | No | Free text. Presence reveals the Deal & Pricing section. |
| Price / model | No | Free text (e.g. "$40k/yr", "per-seat"). Frames the deal section when present. |

All free-text fields are sanitized through a shared guard (see Guardrails)
before they ever reach the prompt.

### 2. Brief contract (dynamic)

`SECTIONS` becomes a function of `(focus, has_product)` via
`build_sections(focus, has_product)`. Order:

1. **Company Snapshot** — always.
2. **Financial Pulse & Trajectory** — always. Web-sourced, qualitative:
   recent stock trend (public) or funding/valuation/growth signals (private),
   recent earnings/investor themes, any upcoming investor events found, and a
   synthesized "where they're heading" read. Every line labeled *as of
   {research date} — verify*. Clean "Private company — no public market data"
   fallback when no signals found.
3. **{Focus} Profile** — always. Title defaults to "Supply Chain & Ops
   Profile"; a focus retitles and retargets it (e.g. "Marketing Profile" →
   martech stack, channels, org shape).
4. **Pain Points & Signals** — always, focus-aware.
5. **Decision-Maker Profiles** — always. Targets chosen to fit the focus (SC
   default; marketing → CMO / VP Demand Gen, etc.). Keeps the existing
   integrity rule: LinkedIn **people-search links only, never invented names**.
6. **Talking Points** — always. Shaped by the call-context line when present.
7. **Deal & Pricing** — **only when a product is provided.** Positioning of the
   named product against the pain found, value framing tied to a specific
   signal, 2–3 likely objections + responses, and a **labeled deal-size band
   estimate** for a company this size (see deal-size anchoring below).
8. **Sources** — always, last. Rendered as a collapsed accordion in the UI.

### 3. Backend architecture

- **Dynamic queries:** `exa_search(company, focus)` builds queries from company
  + focus, plus new finance/earnings templates (stock/earnings/funding). When
  `focus` is blank, the current supply-chain templates are used.
- **Concurrency:** run the Exa queries in a thread pool instead of
  sequentially, so total search latency ≈ one query, not the sum. Keep the
  "one bad query shouldn't kill the brief" behavior per query.
- **Recency bias:** pass Exa `startPublishedDate` (rolling window, e.g. last
  18 months) so pain signals and financials lean recent. Preserve title + URL
  + published date per result through `_format_research` so the model can date
  its claims and the UI can show source dates.
- **Prompt restructure:** `generate_brief(company, focus, call_context,
  product, price)` builds the system prompt from the dynamic section list and
  injects focus/context/product/price into the user turn. Conditional Deal &
  Pricing section included only when `product` is set.
- **Deal-size anchoring:** a `DEAL_SIZE_BANDS` reference table in `config.py`
  (company-size bucket → rough ACV band) is surfaced to the prompt as a
  cheat-sheet. The model picks the band matching the company's size from
  research and presents it as a labeled estimate citing the band. If size is
  unknown, no number — qualitative framing only. This gives the number a
  defined spine without a second structured call.
- **Token ceiling:** raise `MAX_TOKENS` (2600 → ~3400) so the longer brief
  doesn't truncate mid-section; prompt still enforces a "3-minute read" brevity
  rule per section.

### 4. Financial data approach

Web-sourced only — **no new finance API / no new key** (per decision). Groq
synthesizes financials qualitatively from Exa results. Non-negotiable
labeling: no fabricated precise live stock price; trend and earnings framed
qualitatively and dated; private companies get the market-data fallback.

### 5. Frontend / layout

- **Tighten:** collapse the masthead + oversized Playfair headline + lede into
  a compact header. Make the input console the focal point near the top; brief
  renders directly below. Same editorial aesthetic (Playfair + Newsreader,
  cream/rust), tighter vertical rhythm. Built via the design skill.
- **Form:** the five-field form above, with the product/price pair visually
  grouped and clearly optional.
- **Sources accordion:** the Sources section renders inside a
  `<details>/<summary>` disclosure, collapsed by default. Each source shows
  title + date when available, not a bare URL.
- **Copy / export:** a "Copy brief" button (copies the rendered brief as text)
  and a "Print / Save PDF" affordance on the brief header.

### 6. Security hardening (parity with TideStock)

- Security-header middleware: CSP, X-Frame-Options, X-Content-Type-Options
  (nosniff), Referrer-Policy, Permissions-Policy, HSTS. CSP must allow the
  existing CDN (marked, DOMPurify, Google Fonts) and self.
- Disable FastAPI docs: `/docs`, `/redoc`, `/openapi.json` → 404
  (`docs_url=None, redoc_url=None, openapi_url=None`).
- Per-IP rate limit on `POST /api/brief` (mirror TideStock's limiter),
  returning 429. Keeps the cookie session-cap as the UX nudge; the IP limit is
  the real quota guard for the free Exa/Groq tiers.

### 7. Showcase

- Regenerate all 5 existing briefs in the new format (so no half-old/half-new
  inconsistency in the default demo surface).
- Add **one non-supply-chain showcase** (a marketing- or IT-focused brief on a
  recognizable company) so the new focus capability is visible without typing.

## Guardrails (credibility spine)

- **No fabricated hard numbers presented as live.** All financial content and
  the deal-size band are labeled estimates, dated, and framed as "verify."
- **Decision-makers:** search links only, never invented names/emails/phones
  (existing rule, preserved).
- **Sourced claims:** every Pain Points / Financial signal traces to a source
  URL; "No public signals found" instead of invention.
- **Prompt-injection hygiene:** all new free-text fields (focus, call context,
  product, price) pass through the shared sanitizer and are wrapped as clearly
  delimited, untrusted user data in the prompt — never as instructions.

## Testing plan

- Update `test_brief_prompt.py`: assert `build_sections()` — default titles,
  focus retitling section 3, Deal & Pricing present iff product provided,
  Sources always last.
- Update `test_research.py`: new `generate_brief` signature; focus reaches the
  queries; free-text fields reach the user turn; deal-size band cheat-sheet
  present when product set; concurrency doesn't drop results.
- Update `test_api.py`: new request body fields; happy path with/without
  optional fields; sanitization of new fields.
- New `test_security.py`: security headers present on responses; docs
  endpoints 404; per-IP limit returns 429.
- New: deal-size band mapping unit test.
- Keep all mocks offline (no live API, no cost).

## Out of scope / deferred

- Real finance API integration (chosen against — web-sourced instead).
- Groq retry/backoff on transient 503s (note; revisit later).
- Usage logging / analytics for interview metrics (nice-to-have, later).
- Shareable brief permalinks.
- Multi-node / persistent cache (in-process is fine for a demo).

## Decisions locked

- Price quoting: **Both** — rep supplies product + price, AI also adds a
  labeled deal-size band.
- Financials: **web-sourced, no new key**, strictly labeled.
- Generalization: **supply-chain default + optional focus override.**
- Deal & Pricing section appears **only when a product is entered.**
- **All 5 showcase briefs regenerated** + 1 non-SC example added.
- Security parity items (headers, disabled docs, per-IP limit) included in this
  effort.
