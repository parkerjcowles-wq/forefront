"""Forefront — FastAPI app.

Serves the editorial single-page frontend and two JSON endpoints:
  GET  /api/showcase/{slug}  -> pre-generated brief (zero live cost)
  POST /api/brief            -> live brief via Claude + web_search (capped per session)
"""
from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # read .env so GROQ_API_KEY / EXA_API_KEY reach os.environ

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import cache
from app.config import MAX_CUSTOM_BRIEFS, SHOWCASE
from app.research import BriefGenerationError, generate_brief
from app.validate import (
    InvalidCompanyName, request_cache_key, sanitize, sanitize_freetext,
)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
SHOWCASE_DIR = BASE_DIR / "showcase"

SESSION_COOKIE = "ff_sid"

app = FastAPI(
    title="Forefront — Prospect Intelligence Agent",
    docs_url=None, redoc_url=None, openapi_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


class BriefRequest(BaseModel):
    company: str
    focus: str = ""
    call_context: str = ""
    product: str = ""
    price: str = ""


def _session_id(request: Request, response: Response) -> str:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = uuid.uuid4().hex
        response.set_cookie(
            SESSION_COOKIE, sid, max_age=60 * 60 * 24 * 30,
            httponly=True, samesite="lax",
        )
    return sid


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/api/showcase/{slug}")
def get_showcase(slug: str):
    if slug not in SHOWCASE:
        return JSONResponse({"error": "Unknown showcase company."}, status_code=404)
    path = SHOWCASE_DIR / f"{slug}.md"
    if not path.exists():
        return JSONResponse({"error": "Showcase brief not found."}, status_code=404)
    markdown = path.read_text(encoding="utf-8")
    return {"company": SHOWCASE[slug], "markdown": markdown, "showcase": True}


@app.post("/api/brief")
def post_brief(body: BriefRequest, request: Request, response: Response):
    sid = _session_id(request, response)

    if cache.ip_rate_limited(_client_ip(request)):
        return JSONResponse(
            {"error": "Too many requests — slow down and try again shortly.",
             "rate_limited": True},
            status_code=429,
        )

    try:
        company = sanitize(body.company)
    except InvalidCompanyName as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    focus = sanitize_freetext(body.focus)
    call_context = sanitize_freetext(body.call_context)
    product = sanitize_freetext(body.product)
    price = sanitize_freetext(body.price)

    key = request_cache_key(company, focus, call_context, product, price)

    # Free path: a cached brief doesn't count against the session cap.
    cached = cache.cache_get(key)
    if cached is not None:
        return {**cached, "company": company, "cached": True}

    # Billed path: enforce the per-session cap before spending anything.
    if cache.session_at_limit(sid):
        return JSONResponse(
            {
                "error": (
                    f"You've reached the demo limit of {MAX_CUSTOM_BRIEFS} custom "
                    "briefs. Try one of the showcase companies — they're instant."
                ),
                "limit_reached": True,
            },
            status_code=429,
        )

    try:
        result = generate_brief(
            company, focus=focus, call_context=call_context,
            product=product, price=price,
        )
    except BriefGenerationError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    cache.cache_set(key, result)
    cache.increment_session(sid)
    return {**result, "company": company, "cached": False}


# Static frontend mounted last so /api/* routes take precedence.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
