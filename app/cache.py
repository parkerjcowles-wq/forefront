"""In-process TTL cache + per-session custom-brief counter.

Deliberately simple (single process, in-memory) — this is a portfolio demo, not
a multi-node service. Keeps live API calls (and cost) near zero on repeats.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

from app.config import CACHE_TTL_SECONDS, MAX_CUSTOM_BRIEFS, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW

_lock = threading.Lock()
_brief_cache: Dict[str, Tuple[float, dict]] = {}      # key -> (expires_at, value)
_session_counts: Dict[str, int] = {}                  # session id -> custom-brief count
_ip_hits: Dict[str, list] = {}  # ip -> [timestamps]


def cache_get(key: str) -> Optional[dict]:
    with _lock:
        entry = _brief_cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() >= expires_at:
            _brief_cache.pop(key, None)
            return None
        return value


def cache_set(key: str, value: dict) -> None:
    with _lock:
        _brief_cache[key] = (time.time() + CACHE_TTL_SECONDS, value)


def session_count(session_id: str) -> int:
    with _lock:
        return _session_counts.get(session_id, 0)


def session_at_limit(session_id: str) -> bool:
    return session_count(session_id) >= MAX_CUSTOM_BRIEFS


def increment_session(session_id: str) -> int:
    """Count one custom (billed) brief against the session; return new count."""
    with _lock:
        _session_counts[session_id] = _session_counts.get(session_id, 0) + 1
        return _session_counts[session_id]


def ip_rate_limited(ip: str) -> bool:
    """Record one hit for `ip`; return True if it exceeds the window budget."""
    now = time.time()
    with _lock:
        # Evict IPs whose whole window has expired so the table can't grow
        # unbounded from one-off visitors/bots on a long-lived process.
        for stale in [k for k, ts in _ip_hits.items()
                      if not ts or now - ts[-1] >= RATE_LIMIT_WINDOW]:
            del _ip_hits[stale]
        hits = [t for t in _ip_hits.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
        hits.append(now)
        _ip_hits[ip] = hits
        return len(hits) > RATE_LIMIT_MAX


def reset() -> None:
    """Clear all state — used by tests."""
    with _lock:
        _brief_cache.clear()
        _session_counts.clear()
        _ip_hits.clear()
