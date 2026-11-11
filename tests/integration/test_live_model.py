"""Integration tests against the REAL configured model endpoint.

Run explicitly:  RESEARCHOPS_INTEGRATION=1 pytest tests/integration -q
Skipped in normal runs and in CI. Mocked tests never claim to validate model
behavior (see docs/ai_governance.md).
"""

from __future__ import annotations

import os
import pathlib
import sys

import fitz
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.api.routes import create_app  # noqa: E402
from app.config import AppConfig, LLMConfig  # noqa: E402
from scripts.generate_protocols import PROTOCOL_A  # noqa: E402

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RESEARCHOPS_INTEGRATION") != "1",
        reason="set RESEARCHOPS_INTEGRATION=1 with LLM_* env to run live-model tests",
    ),
]


@pytest.fixture(scope="module")
def live_client(tmp_path_factory):
    cfg = AppConfig(
        db_path=tmp_path_factory.mktemp("int") / "int.db",
        data_dir=tmp_path_factory.mktemp("data"),
        llm=LLMConfig(),  # from the real environment
    )
    if not cfg.llm.is_configured():
        pytest.fail("LLM_* env vars not set; integration run aborted")
    with TestClient(create_app(cfg)) as c:
        yield c


def _upload_real_protocol(client: TestClient) -> str:
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    for title, paras in PROTOCOL_A["sections"][:6]:
        if y > 700:
            page = doc.new_page()
            y = 60
        page.insert_textbox(fitz.Rect(50, y, 545, y + 16), title.upper(), fontsize=10)
        y += 18
        page.insert_textbox(fitz.Rect(50, y, 545, min(y + 180, 740)), " ".join(paras), fontsize=9)
        y += 200
    data = doc.tobytes()
    doc.close()
    r = client.post("/api/documents", files={"file": ("lung.pdf", data, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["doc_id"]


def test_live_extraction_and_qa(live_client: TestClient) -> None:
    doc_id = _upload_real_protocol(live_client)

    r = live_client.post(f"/api/documents/{doc_id}/analyze")
    assert r.status_code == 200, r.text
    extraction = r.json()["extraction"]
    gt = PROTOCOL_A["ground_truth"]  # synthetic doc: ground truth is known
    assert gt["protocol_id"] in extraction["protocol_id"]["value"]
    assert "120" in extraction["planned_enrollment"]["value"]

    q = live_client.post(
        f"/api/documents/{doc_id}/ask",
        json={"question": "How many participants will be enrolled?"},
    )
    assert q.status_code == 200, q.text
    answer = q.json()
    assert answer["answer"]
    assert isinstance(answer["citations"], list) and answer["citations"]

    pdf = live_client.get(f"/api/documents/{doc_id}/report.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
