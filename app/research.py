"""The research engine: Exa (web search) + Groq (synthesis) — both free tiers.

`search_company()` pulls live web results from Exa; `generate_brief()` feeds those
excerpts to a Groq Llama model that writes the brief. Both the searcher and the Groq
client are injectable so tests run fully offline.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

import requests

from app.brief_prompt import build_system_prompt, build_user_message
from app.config import (
    DEFAULT_QUERY_TEMPLATES,
    FINANCE_QUERY_TEMPLATES,
    EXA_RECENCY_DAYS,
    EXA_RESULTS_PER_QUERY,
    EXA_SNIPPET_CHARS,
    EXA_TIMEOUT,
    EXA_URL,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    MAX_TOKENS,
)

_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")


class BriefGenerationError(RuntimeError):
    """Raised when a brief could not be generated."""


# --- Web search (Exa) -------------------------------------------------------

def _build_queries(company: str, focus: str) -> list[str]:
    base = DEFAULT_QUERY_TEMPLATES if not focus.strip() else [
        "{company} " + focus.strip() + " team leadership organization",
        "{company} " + focus.strip() + " strategy priorities 2025 2026",
        "{company} " + focus.strip() + " software tools technology stack",
        "{company} " + focus.strip() + " challenges news 2025 2026",
    ]
    return [t.format(company=company) for t in (*base, *FINANCE_QUERY_TEMPLATES)]


def _recency_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=EXA_RECENCY_DAYS)).strftime("%Y-%m-%d")


def _run_query(query: str, api_key: str, start_date: str) -> list[dict]:
    base = {
        "query": query,
        "numResults": EXA_RESULTS_PER_QUERY,
        "useAutoprompt": True,
        "type": "neural",
        "contents": {"text": {"maxCharacters": EXA_SNIPPET_CHARS}},
    }

    def _post(payload: dict) -> list[dict]:
        resp = requests.post(
            EXA_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=EXA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    try:
        results = _post({**base, "startPublishedDate": start_date})
        # The recency filter also drops undated pages (e.g. evergreen overview
        # pages for thinly-covered companies). If it returned nothing, retry
        # once unfiltered so a niche/private company doesn't come back empty.
        if not results:
            results = _post(base)
        return results
    except requests.RequestException:
        return []  # one bad query shouldn't kill the brief


def exa_search(company: str, focus: str = "") -> list[dict]:
    """Run focus + finance queries concurrently; return deduped dated results."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        raise BriefGenerationError(
            "EXA_API_KEY is not set. Add it to .env (free key from exa.ai)."
        )
    queries = _build_queries(company, focus)
    start_date = _recency_date()
    seen: set = set()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = pool.map(lambda q: _run_query(q, api_key, start_date), queries)
    for batch in batches:
        for res in batch:
            url = (res.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            results.append({
                "title": (res.get("title") or "").strip(),
                "url": url,
                "text": (res.get("text") or "").strip(),
                "published": (res.get("publishedDate") or "").strip(),
            })
    return results


def _format_research(results: List[dict]) -> str:
    lines: List[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or "(untitled)"
        date = f" ({r['published']})" if r.get("published") else ""
        lines.append(
            f"[{i}] {title}{date}\nURL: {r.get('url', '')}\n{r.get('text', '')}".strip()
        )
    return "\n\n".join(lines)


# --- Synthesis (Groq) -------------------------------------------------------

def get_groq_client():
    """Construct a real Groq client (reads GROQ_API_KEY from env)."""
    import groq  # imported lazily so tests never need a key

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise BriefGenerationError(
            "GROQ_API_KEY is not set. Add it to .env (free key from console.groq.com)."
        )
    return groq.Groq(api_key=api_key)


def _is_profile_url(url: str) -> bool:
    """A specific person's LinkedIn profile — not a citable source for a brief.

    LinkedIn people-*search* links (/search/results/people/) stay; those are the
    decision-maker links. Only individual /in/ profiles are filtered out.
    """
    return "linkedin.com/in/" in url.lower()


def _parse_sources(markdown: str, results: List[dict]) -> List[str]:
    """Unique source URLs: those cited in the brief, else fall back to all results."""
    seen = set()
    out: List[str] = []
    for url in _URL_RE.findall(markdown or ""):
        url = url.rstrip(".,);")
        if url not in seen and not _is_profile_url(url):
            seen.add(url)
            out.append(url)
    if not out:
        for r in results:
            u = r.get("url", "")
            if u and u not in seen and not _is_profile_url(u):
                seen.add(u)
                out.append(u)
    return out


def generate_brief(
    company: str,
    *,
    focus: str = "",
    call_context: str = "",
    product: str = "",
    price: str = "",
    groq_client=None,
    searcher: Optional[Callable[..., List[dict]]] = None,
) -> dict:
    """Generate a sourced account brief. Returns {"markdown", "sources"}."""
    search = searcher or exa_search
    try:
        try:
            results = search(company, focus)          # focus-aware searcher
        except TypeError:
            results = search(company)                 # test searchers take company only
    except BriefGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BriefGenerationError(f"Web search failed: {exc}") from exc

    if not results:
        raise BriefGenerationError(
            "No web results found for that company — check the spelling or try another."
        )

    if groq_client is None:
        groq_client = get_groq_client()

    has_product = bool(product.strip())
    system_prompt = build_system_prompt(focus, has_product)
    user_msg = build_user_message(
        company, _format_research(results), focus=focus,
        call_context=call_context, product=product, price=price,
    )

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=GROQ_TEMPERATURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        markdown = (completion.choices[0].message.content or "").strip()
    except BriefGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BriefGenerationError(f"The synthesis service hit an error: {exc}") from exc

    if not markdown:
        raise BriefGenerationError(
            "No brief was returned — try again or pick a showcase company."
        )
    return {"markdown": markdown, "sources": _parse_sources(markdown, results)}
