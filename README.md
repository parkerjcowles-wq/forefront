# Forefront — Prospect Intelligence Agent

Type a company name; get a sourced, one-page **sales account brief** — the 30–60 minute
pre-call research an account executive does before a discovery call, in seconds.
Exa searches the live web for real sources and Groq's Llama writes the brief: company
snapshot, supply-chain/ops profile, sourced pain signals, decision-makers, and three
talking points that tie a real signal to an opening discovery question.

Built as a portfolio piece for technical B2B sales (supply chain / logistics software).

## Stack

- **Backend:** FastAPI (Python) — `app/`
- **Engine (free):** Exa neural web search (live sources) → Groq `llama-3.3-70b-versatile`
  synthesizes the brief. Both run on generous free tiers.
- **Frontend:** bespoke static HTML/CSS/JS — `web/` (editorial "briefing" aesthetic:
  Playfair Display + Newsreader, cream paper, rust accent)
- **No database** — in-process cache + pre-generated showcase briefs

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # use requirements.txt for prod-only
cp .env.example .env                        # then add your key in an editor
uvicorn app.main:app --reload               # http://127.0.0.1:8000
```

Add your keys to `.env` (never commit it) — both are free:

```
GROQ_API_KEY=gsk_...      # console.groq.com → API Keys
EXA_API_KEY=...           # exa.ai → Dashboard → API Keys
```

The five **showcase companies** (project44, Flexport, Kinaxis, Honeywell, Lindt) render
instantly from committed Markdown and need **no API key** — handy for demos.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q          # 27 tests, Groq client + Exa search fully mocked (no live API, no cost)
```

## Cost (free)

Both providers run on free tiers — Groq's free API and Exa's free search quota — so live
briefs cost nothing. Three controls also keep usage modest and the demo fast:

1. **Showcase briefs** are committed Markdown — most clicks make no API calls at all.
2. **In-process cache** — repeat lookups within 24h reuse the prior result.
3. **Per-session cap** — `MAX_CUSTOM_BRIEFS` (default 3) custom briefs per browser session.

If you ever exceed a free tier, the call simply fails with a friendly message — no charge.

## Deploy (Render free web service)

FastAPI doesn't run on Streamlit Cloud. On [Render](https://render.com):

- New **Web Service** from the repo
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `GROQ_API_KEY`, `EXA_API_KEY`
- Free tier cold-starts after idle (~30s first load) — fine for a portfolio link.

## Security

- API keys live only in `GROQ_API_KEY` / `EXA_API_KEY` (local `.env`, gitignored; host env
  vars on deploy). The browser never sees them — all calls go through the FastAPI backend.
- Company names are sanitized (`app/validate.py`) before entering the prompt.

## Layout

```
app/        FastAPI app, research engine, prompt, validation, cache, config
web/        editorial single-page frontend
showcase/   5 pre-generated briefs (Markdown)
tests/      pytest suite (mocked Anthropic client)
```
