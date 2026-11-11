"""Parse PDF/DOCX uploads into chunks with provenance.

PDF: one chunk per logical block, page number preserved (PyMuPDF).
DOCX: heading/paragraph structure preserved; page numbers are NOT invented.

Empty or unreadable documents raise ParseError — never silently processed.
Scanned (image-only) PDFs are detected and reported: OCR is out of scope.
"""

from __future__ import annotations

import uuid

import fitz  # PyMuPDF
from docx import Document as Docx

from app.models.analysis import DocumentChunk, ParsedDocument

MIN_CHARS_PER_PAGE = 40  # below this a PDF page is probably scanned imagery


class ParseError(Exception):
    pass


def _chunk_id(doc_id: str, page: int | None, index: int) -> str:  # type: ignore[valid-type]
    loc = f"p{page}" if page is not None else "x"
    return f"{doc_id}-{loc}-c{index}"


def _clean(text: str) -> str:  # type: ignore[valid-type]
    return " ".join(text.split())


def parse_pdf(data: bytes, doc_id: str, filename: str) -> ParsedDocument:  # type: ignore[valid-type]
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"unreadable PDF: {exc}") from exc

    if doc.page_count == 0:
        raise ParseError("PDF has no pages")

    chunks: list[DocumentChunk] = []
    empty_pages = 0
    idx = 0
    current_section = ""
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        if len(_clean(text)) < MIN_CHARS_PER_PAGE:
            empty_pages += 1
            continue
        blocks = page.get_text("blocks") or []
        for block in blocks:
            body = _clean(str(block[4]))
            if len(body) < 20:
                continue
            # ALL-CAPS short blocks are treated as section headings
            if len(body) < 80 and body.upper() == body and any(c.isalpha() for c in body):
                current_section = body.title()
            chunks.append(
                DocumentChunk(
                    chunk_id=_chunk_id(doc_id, page_num, idx),
                    doc_id=doc_id,
                    text=body,
                    page=page_num,
                    section=current_section,
                )
            )
            idx += 1
    doc.close()

    if not chunks:
        hint = (
            "document appears to be scanned images; OCR is required and is out of scope"
            if empty_pages
            else "no extractable text found"
        )
        raise ParseError(hint)

    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type="pdf",
        num_pages=max((c.page for c in chunks if c.page is not None), default=0),
        chunks=chunks,
        metadata={},
        warning=f"{empty_pages} sparse page(s)" if empty_pages else "",
    )


def parse_docx(data: bytes, doc_id: str, filename: str) -> ParsedDocument:  # type: ignore[valid-type]
    import io

    try:
        doc = Docx(io.BytesIO(data))
    except Exception as exc:
        raise ParseError(f"unreadable DOCX: {exc}") from exc

    chunks: list[DocumentChunk] = []
    section = ""
    idx = 0
    for para in doc.paragraphs:
        text = _clean(para.text)
        if not text:
            continue
        if para.style is not None and str(para.style.name).lower().startswith("heading"):
            section = text
        if len(text) < 20:
            continue
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id(doc_id, None, idx),
                doc_id=doc_id,
                text=text,
                page=None,  # DOCX has no page numbers; we do not invent them
                section=section,
            )
        )
        idx += 1

    if not chunks:
        raise ParseError("no readable paragraphs in DOCX")

    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type="docx",
        num_pages=0,
        chunks=chunks,
        metadata={"core_properties": str(doc.core_properties.title or "")},
    )


def parse_document(data: bytes, doc_type: str, filename: str) -> ParsedDocument:  # type: ignore[valid-type]
    doc_id = uuid.uuid4().hex[:12]
    if doc_type == "pdf":
        return parse_pdf(data, doc_id, filename)
    if doc_type == "docx":
        return parse_docx(data, doc_id, filename)
    raise ParseError(f"unknown type {doc_type}")
