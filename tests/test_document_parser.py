from __future__ import annotations

import fitz
import pytest

from app.services.document_parser import ParseError, parse_document, parse_docx, parse_pdf
from tests.conftest import docx_bytes, pdf_bytes


def test_pdf_parse_pages_and_chunks():
    doc = parse_pdf(pdf_bytes(), "doc1", "t.pdf")
    assert doc.doc_type == "pdf"
    assert doc.num_pages >= 1
    assert all(c.page is not None for c in doc.chunks)
    ids = [c.chunk_id for c in doc.chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"


def test_docx_parse_no_page_numbers():
    doc = parse_docx(
        docx_bytes(["Paragraph one with enough content for a chunk to be formed."]), "d2", "t.docx"
    )
    assert doc.doc_type == "docx"
    assert all(c.page is None for c in doc.chunks), "DOCX page numbers must not be invented"
    assert doc.chunks[0].section == "Test Document"


def test_empty_pdf_rejected():
    empty = b"%PDF-1.4\n%%EOF"  # signature ok, no pages
    with pytest.raises(ParseError):
        parse_pdf(empty, d3 := "d3", "e.pdf")  # noqa: F841


def test_corrupt_pdf_rejected():
    with pytest.raises(ParseError):
        parse_pdf(b"not a pdf at all", "d4", "c.pdf")


def test_image_only_pdf_reports_ocr_need():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(0, 0, 400, 400), pixmap=fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10)))
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ParseError) as e:
        parse_pdf(data, "d5", "scan.pdf")
    assert "OCR" in str(e.value)


def test_unsupported_type():
    import pytest as _pytest

    with _pytest.raises(ParseError):
        parse_document(b"x", "txt", "f.txt")
