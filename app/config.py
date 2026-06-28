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
MAX_TOKENS = 2600  # Llama output ceiling for one brief

# Exa neural search
EXA_URL = "https://api.exa.ai/search"
EXA_RESULTS_PER_QUERY = 6
EXA_SNIPPET_CHARS = 600
EXA_TIMEOUT = 12

# The Exa queries run per company ({company} is substituted). These shape the
# brief: overview, software stack, pain signals, and hiring (best investment signal).
EXA_QUERY_TEMPLATES = [
    "{company} company overview operations supply chain",
    "{company} ERP WMS TMS supply chain planning software stack",
    "{company} supply chain challenges restructuring layoffs news 2025 2026",
    "{company} hiring supply chain planner analyst job posting",
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
