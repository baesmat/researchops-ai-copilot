"""Defensive text handling for untrusted document content.

Uploaded documents are treated as evidence, never as instructions: before any
document text reaches a prompt it is passed through ``sanitize_for_prompt``,
which strips control characters and demotes imperative patterns. The system
prompt (written by us) is always kept in a separate message from document
content (user data), and citations are validated against known chunk ids.
"""

from __future__ import annotations

import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_for_prompt(text: str, max_chars: int = 6000) -> str:
    """Make arbitrary document text safe to embed in a prompt."""
    cleaned = CONTROL_CHARS.sub(" ", text)
    # collapse the "ignore previous instructions"-style noise without
    # interpreting it: it is data, the system prompt governs behavior.
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()[:max_chars]


def sanitize_question(question: str, max_chars: int = 2000) -> str:
    """User questions are also untrusted; normalize before prompting."""
    return CONTROL_CHARS.sub(" ", question).strip()[:max_chars]


def valid_chunk_id(chunk_id: str, known: set[str]) -> bool:
    return bool(chunk_id) and chunk_id in known
