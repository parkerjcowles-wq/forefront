"""Central configuration for Forefront — the Prospect Intelligence Agent.

Mirrors TideStock's pattern: a single module of constants, no Streamlit/web
imports so it stays trivially importable from tests.
"""
from __future__ import annotations

import os

# --- Engine: Exa (web search) + Groq (synthesis), both free tiers -----------
# Groq's free-tier Llama writes the brief from web results that Exa pulls.
GROQ_MODEL = os.environ.get("FOREFRONT_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = 0.4
MAX_TOKENS = 3400  # Llama output ceiling for one (now longer) brief

# Exa neural search
EXA_URL = "https://api.exa.ai/search"
EXA_RESULTS_PER_QUERY = 6
EXA_SNIPPET_CHARS = 600
EXA_TIMEOUT = 12

# Recency: only surface material published within this window (days).
EXA_RECENCY_DAYS = 550  # ~18 months

# Default (supply-chain/ops) query templates — used when no focus is given.
DEFAULT_QUERY_TEMPLATES = [
    "{company} company overview operations supply chain",
    "{company} ERP WMS TMS supply chain planning software stack",
    "{company} supply chain challenges restructuring layoffs news 2025 2026",
    "{company} hiring supply chain planner analyst job posting",
]

# Financial-pulse queries — always run, in addition to the focus queries.
FINANCE_QUERY_TEMPLATES = [
    "{company} stock price earnings report results 2025 2026",
    "{company} revenue funding valuation financial performance",
]

# --- Cost / abuse controls ---------------------------------------------------
# Custom (non-showcase) briefs allowed per browser session before we nudge
# visitors to the always-free showcase companies.
MAX_CUSTOM_BRIEFS = 3

# In-process cache TTL for custom lookups (seconds). 24h.
CACHE_TTL_SECONDS = 60 * 60 * 24

# --- Showcase companies (pre-generated, committed, zero live cost) -----------
# slug -> display name. These are the default demo surface.
SHOWCASE = {
    "project44": "project44",
    "flexport": "Flexport",
    "kinaxis": "Kinaxis",
    "honeywell": "Honeywell",
    "lindt": "Lindt & Sprüngli",
    "hubspot-marketing": "HubSpot (Marketing focus)",
}

# --- Target verticals (domain cheat-sheet, surfaced to the model) ------------
TARGET_VERTICALS = {
    "Supply chain software": "Their own product; pain = competitive displacement, upsell",
    "Logistics tech": "Custom/homegrown stack; pain = visibility, carrier API integrations",
    "Industrial": "SAP ECC or S/4HANA; pain = aging ERP, spare-parts complexity",
    "CPG": "SAP APO/IBP; pain = demand forecasting, promo volatility",
    "Automotive": "SAP + custom MES; pain = just-in-time disruption, supplier risk",
}

# Input guard: longest company name we'll accept before treating it as junk.
MAX_COMPANY_NAME_LEN = 80

# Longest free-text value we accept for the optional fields (focus, call
# context, product, price). Interpolated into the prompt, so kept short.
MAX_FREE_TEXT_LEN = 200

# Deal-size cheat-sheet surfaced to the model so the estimate has a defined
# spine. Company-size bucket -> rough annual-contract-value band.
DEAL_SIZE_BANDS = {
    "smb": "under ~200 employees -> ~$5k-$25k ACV",
    "mid": "~200-2,000 employees -> ~$25k-$100k ACV",
    "enterprise": "~2,000-20,000 employees -> ~$100k-$500k ACV",
    "global": "20,000+ employees -> ~$500k+ ACV",
}

# Per-IP rate limit on live-brief generation (protects free Exa/Groq quotas).
RATE_LIMIT_MAX = 20        # requests
RATE_LIMIT_WINDOW = 60     # seconds
