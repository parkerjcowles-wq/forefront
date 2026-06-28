"""Input sanitization for company names.

The cleaned name is interpolated into the model prompt, so this is the
prompt-injection / junk-input guard. Keep it strict and dependency-free.
"""
from __future__ import annotations

import re
import unicodedata

from app.config import MAX_COMPANY_NAME_LEN


class InvalidCompanyName(ValueError):
    """Raised when a submitted company name can't be used."""


# Allow letters, numbers, spaces and a small set of punctuation real company
# names use (& . , ' - + and parentheses). Everything else is stripped.
_ALLOWED = re.compile(r"[^0-9A-Za-zÀ-ɏ &.,'\-+()]")
_WHITESPACE = re.compile(r"\s+")


def sanitize(raw: str) -> str:
    """Return a clean company name or raise InvalidCompanyName.

    - strips control characters and disallowed symbols
    - collapses whitespace
    - enforces a length cap (junk / injection guard)
    """
    if raw is None:
        raise InvalidCompanyName("No company name provided.")

    # Normalize unicode. Turn any whitespace (tabs, newlines) into plain spaces
    # FIRST so the control-char strip below doesn't glue words together.
    text = unicodedata.normalize("NFKC", str(raw))
    text = _WHITESPACE.sub(" ", text)

    # Drop remaining control/format characters (category starting "C").
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))

    text = _ALLOWED.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()

    if not text:
        raise InvalidCompanyName("Enter a company name to generate a brief.")

    if len(text) > MAX_COMPANY_NAME_LEN:
        raise InvalidCompanyName(
            f"That name is too long (max {MAX_COMPANY_NAME_LEN} characters)."
        )

    # Require at least one alphanumeric character — reject pure punctuation.
    if not any(ch.isalnum() for ch in text):
        raise InvalidCompanyName("Enter a real company name.")

    return text


def cache_key(name: str) -> str:
    """Normalized key for caching (case/space-insensitive)."""
    return _WHITESPACE.sub(" ", name).strip().lower()
