"""Upload validation: type allow-list, signature check, size cap, safe names.

Defense philosophy: uploaded documents are untrusted data. Nothing from an
upload is executed; only bytes are parsed by the PDF/DOCX libraries.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TYPES = {"pdf": b"%PDF", "docx": b"PK\x03\x04"}

MAX_NAME_LEN = 120


class ValidationError(Exception):
    pass


@dataclass
class ValidatedUpload:
    filename: str  # sanitized
    doc_type: str  # pdf | docx
    content: bytes


def sanitize_filename(name: str) -> str:
    """Normalize to a conservative filename; no paths, no surprises."""
    name = unicodedata.normalize("NFKC", name or "document")
    name = Path(name).name  # strip any directory components (path traversal)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.lstrip(".")[:MAX_NAME_LEN]
    return name or "document"


def validate_upload(filename: str, content: bytes, max_bytes: int) -> ValidatedUpload:
    if not content:
        raise ValidationError("empty file")
    if len(content) > max_bytes:
        raise ValidationError(
            f"file too large ({len(content) // 1024 // 1024} MB); limit is {max_bytes // 1024 // 1024} MB"
        )

    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_TYPES:
        raise ValidationError(f"unsupported file type '.{suffix}' (allowed: pdf, docx)")

    signature = ALLOWED_TYPES[suffix]
    if not content.startswith(signature):
        # common real-world case: .doc/.pdf-named files that are something else
        raise ValidationError(
            f"file signature does not match declared type '.{suffix}' (corrupt or mislabeled?)"
        )

    return ValidatedUpload(filename=sanitize_filename(filename), doc_type=suffix, content=content)
