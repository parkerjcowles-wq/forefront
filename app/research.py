"""The research engine: Exa (web search) + Groq (synthesis) — both free tiers.

`search_company()` pulls live web results from Exa; `generate_brief()` feeds those
excerpts to a Groq Llama model that writes the brief. Both the searcher and the Groq
client are injectable so tests run fully offline.
"""
from __future__ import annotations

import os
import re
from typing import Callable, List, Optional

import requests

from app.brief_prompt import SYSTEM_PROMPT, build_user_message
from app.config import (
    EXA_QUERY_TEMPLATES,
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

def exa_search(company: str) -> List[dict]:
    """Run the per-company Exa queries; return deduped [{title, url, text}]."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        raise BriefGenerationError(
            "EXA_API_KEY is not set. Add it to .env (free key from exa.ai)."
        )

    seen: set = set()
    results: List[dict] = []
    for template in EXA_QUERY_TEMPLATES:
        query = template.format(company=company)
        try:
            resp = requests.post(
                EXA_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": EXA_RESULTS_PER_QUERY,
                    "useAutoprompt": True,
                    "type": "neural",
                    "contents": {"text": {"maxCharacters": EXA_SNIPPET_CHARS}},
                },
                timeout=EXA_TIMEOUT,
            )
            resp.raise_for_status()
            for res in resp.json().get("results", []):
                url = (res.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                results.append({
                    "title": (res.get("title") or "").strip(),
                    "url": url,
                    "text": (res.get("text") or "").strip(),
                })
        except requests.RequestException:
            # One bad query shouldn't kill the brief — keep what we have.
            continue
    return results


def _format_research(results: List[dict]) -> str:
    """Turn Exa results into a numbered, source-tagged context block."""
    lines: List[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or "(untitled)"
        lines.append(f"[{i}] {title}\nURL: {r.get('url', '')}\n{r.get('text', '')}".strip())
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


def _parse_sources(markdown: str, results: List[dict]) -> List[str]:
    """Unique source URLs: those cited in the brief, else fall back to all results."""
    seen = set()
    out: List[str] = []
    for url in _URL_RE.findall(markdown or ""):
        url = url.rstrip(".,);")
        if url not in seen:
            seen.add(url)
            out.append(url)
    if not out:
        for r in results:
            u = r.get("url", "")
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def generate_brief(
    company: str,
    groq_client=None,
    searcher: Optional[Callable[[str], List[dict]]] = None,
) -> dict:
    """Generate a sourced account brief for `company`.

    Returns {"markdown": str, "sources": [str]}. Raises BriefGenerationError.
    `groq_client` and `searcher` are injectable for offline testing.
    """
    search = searcher or exa_search
    try:
        results = search(company)
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

    user_msg = build_user_message(company, _format_research(results))

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=GROQ_TEMPERATURE,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        markdown = (completion.choices[0].message.content or "").strip()
    except BriefGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface a clean message to the API layer
        raise BriefGenerationError(f"The synthesis service hit an error: {exc}") from exc

    if not markdown:
        raise BriefGenerationError(
            "No brief was returned — try again or pick a showcase company."
        )

    return {"markdown": markdown, "sources": _parse_sources(markdown, results)}
