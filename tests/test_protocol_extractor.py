from __future__ import annotations

import pytest

from app.models.analysis import NOT_SPECIFIED, ExtractionField, ProtocolExtraction
from app.services.checklist_generator import build_checklist, to_csv
from app.services.llm_client import LLMError, extract_from_llm, parse_json_lenient
from app.services.protocol_extractor import _supports, _verify


def _extraction(**overrides) -> ProtocolExtraction:  # type: ignore[valid-type]
    ex = ProtocolExtraction(doc_id="d1")
    ex.study_type = ExtractionField(value="Interventional")
    ex.protocol_id = ExtractionField(value="DEMO-T-001", source_chunk_ids=["d-p1-c0"], verified=True)
    ex.planned_enrollment = ExtractionField(value="120 participants", source_chunk_ids=["d-p1-c1"], verified=True)
    ex.regulatory = ExtractionField(value="IRB approval required", source_chunk_ids=["d-p1-c2"], verified=True)
    ex.imaging = ExtractionField(value=NOT_SPECIFIED)
    for k, v in overrides.items():
        setattr(ex, k, v)
    return ex


def _chunks_by_id() -> dict:  # type: ignore[valid-type]
    from app.models.analysis import DocumentChunk

    return {
        f"d-p1-c{i}": DocumentChunk(
            chunk_id=f"d-p1-c{i}", doc_id="d", text=text, page=1, section="S"
        )
        for i, text in enumerate(
            [
                "Protocol identifier DEMO-T-001 version 1.",
                "The study plans enrollment of 120 participants in total.",
                "The protocol requires IRB approval prior to activation.",
            ]
        )
    }


def test_extract_from_llm_maps_and_validates_citations():
    payload = {
        "protocol_id": {"value": "DEMO-T-001", "source_chunk_ids": ["d-p1-c0"]},
        "planned_enrollment": {"value": 120, "source_chunk_ids": ["d-p1-c1", "unknown-id"]},
        "sponsor": "Acme (fictional)",  # bare string form
        "study_phase": None,  # missing -> NOT_SPECIFIED
        "missing_information": ["site labs unspecified"],
    }
    out = extract_from_llm(payload, {"d-p1-c0", "d-p1-c1"})
    f = out["fields"]
    assert f["protocol_id"]["value"] == "DEMO-T-001"
    assert f["protocol_id"]["source_chunk_ids"] == ["d-p1-c0"]
    assert f["planned_enrollment"]["value"] == "120"
    assert set(f["planned_enrollment"]["source_chunk_ids"]) == {"d-p1-c1"}  # unknown dropped
    assert f["study_phase"]["value"] == NOT_SPECIFIED
    assert f["sponsor"]["value"].startswith("Acme")
    assert out["missing_information"] == ["site labs unspecified"]


def test_parse_json_lenient_repairs_fences():
    assert parse_json_lenient('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_lenient('noise before {"a": {"b": 2}} noise after') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        parse_json_lenient("not json at all")


def test_support_and_verification():
    chunk = _chunks_by_id()["d-p1-c1"]
    assert _supports("enrollment of 120 participants", chunk.text)
    assert not _supports("pancreatic surgery staging", chunk.text)

    ok = _verify(
        ExtractionField(value="enrollment of 120 participants", source_chunk_ids=["d-p1-c1", "d-p1-c0"]),
        _chunks_by_id(),
    )
    assert ok.verified and ok.source_chunk_ids == ["d-p1-c1"]

    unsupported = _verify(
        ExtractionField(value="pancreatic surgery staging", source_chunk_ids=["d-p1-c1"]),
        _chunks_by_id(),
    )
    assert not unsupported.verified and not unsupported.source_chunk_ids


def test_checklist_classification_and_structure():
    ex = _extraction()
    ex.missing_information = ["timeline undefined"]
    items = build_checklist(ex, _chunks_by_id())
    types = {i["task_type"] for i in items}
    assert types <= {"Protocol Required", "AI Suggested", "Needs Clarification"}
    assert any(i["task_type"] == "Protocol Required" for i in items)
    assert any(i["task_type"] == "AI Suggested" for i in items)
    # missing imaging + explicit missing note => clarification items
    assert any(i["task_type"] == "Needs Clarification" for i in items)
    for item in items:
        assert item["requires_human_review"] is True
        assert item["status"] == "Not Started"
        assert item["category"]

def test_checklist_missing_becomes_clarification():
    ex = _extraction()
    ex.planned_enrollment = ExtractionField(value=NOT_SPECIFIED)
    items = build_checklist(ex, _chunks_by_id(), ai_suggestions=False)
    clarification = [i for i in items if i["task_type"] == "Needs Clarification"]
    assert any("enrollment" in i["task"].lower() for i in clarification)


def test_csv_export():
    import csv
    import io

    items = build_checklist(_extraction(), _chunks_by_id())
    rows = list(csv.DictReader(io.StringIO(to_csv(items))))
    assert len(rows) == len(items)
    assert set(rows[0]) == {
        "id", "task", "category", "priority", "status", "source_reference",
        "rationale", "task_type", "requires_human_review",
    }
