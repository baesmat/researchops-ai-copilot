"""Shared fixtures: temp config, app client, synthetic PDF/DOCX builders."""

from __future__ import annotations

import io
import pathlib

import fitz
import pytest
from docx import Document as Docx
from fastapi.testclient import TestClient

from app.api.routes import create_app
from app.config import AppConfig


def make_cfg(tmp_path: pathlib.Path, **overrides) -> AppConfig:
    cfg = AppConfig(
        db_path=tmp_path / "test.db",
        data_dir=tmp_path / "data",
        max_upload_mb=1,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def make_client(tmp_path: pathlib.Path, **overrides) -> TestClient:
    return TestClient(create_app(make_cfg(tmp_path, **overrides)))


def pdf_bytes(title: str = "Test Protocol", sections: dict[str, list[str]] | None = None) -> bytes:  # type: ignore[valid-type]
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    page.insert_textbox(fitz.Rect(50, 30, 540, 50), title, fontsize=13)
    for heading, paras in (sections or {"Body": ["This is a test paragraph with content."] * 3}).items():
        page.insert_textbox(fitz.Rect(50, y, 540, y + 16), heading.upper(), fontsize=10)
        y += 20
        body = " ".join(paras)
        leftover = page.insert_textbox(fitz.Rect(50, y, 540, 760), body, fontsize=9)
        if leftover < 0:
            page2 = doc.new_page()
            page2.insert_textbox(fitz.Rect(50, 60, 540, 760), body, fontsize=9)
        y += 240
    data = doc.tobytes()
    doc.close()
    return data


def docx_bytes(paragraphs: list[str]) -> bytes:  # type: ignore[valid-type]
    doc = Docx()
    doc.add_heading("Test Document", level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path: pathlib.Path):
    with make_client(tmp_path) as c:
        yield c


def upload_pdf(client: TestClient, name: str = "t.pdf", **kwargs) -> dict:  # type: ignore[valid-type]
    return client.post(
        "/api/documents",
        files={"file": (name, pdf_bytes(**kwargs), "application/pdf")},
    )
