"""Study-startup checklist generation.

Deterministic 'Protocol Required' items are derived from extracted fields with
verified citations. 'Needs Clarification' items come from missing information.
'AI Suggested' items are optional operational considerations. AI suggestions
are never presented as regulatory requirements; everything carries
requires_human_review.
"""

from __future__ import annotations

import uuid

from app.models.analysis import (
    NOT_SPECIFIED,
    ChecklistItem,
    ExtractionField,
    ProtocolExtraction,
)
from app.services.protocol_extractor import FIELD_TO_LABEL

CATEGORY_OF = {
    "regulatory": "Regulatory and Governance",
    "imaging": "Clinical and Technical Dependencies",
    "laboratory": "Clinical and Technical Dependencies",
    "biospecimen": "Clinical and Technical Dependencies",
    "data_storage": "Research Informatics",
    "data_sharing": "Research Informatics",
    "external_collaboration": "Research Informatics",
    "specialized_computing": "Research Informatics",
    "software_dependencies": "Research Informatics",
}

# field -> (task template, priority)
REQUIRED_TASKS = {
    "regulatory": ("Confirm {value} requirements and required approvals", "High"),
    "imaging": ("Confirm imaging workflow and storage requirements: {value}", "High"),
    "laboratory": ("Set up laboratory processing for: {value}", "High"),
    "biospecimen": ("Arrange biospecimen collection, labeling and shipment: {value}", "High"),
    "data_storage": ("Provision data storage per protocol: {value}", "High"),
    "data_sharing": ("Establish data-sharing agreements: {value}", "Medium"),
    "external_collaboration": ("Onboard external collaborators: {value}", "Medium"),
    "specialized_computing": ("Evaluate specialized computing needs: {value}", "Medium"),
    "software_dependencies": ("Validate software dependencies: {value}", "Medium"),
}

AI_SUGGESTED = [
    ChecklistItem(
        task="Draft study startup timeline with owner per task",
        category="Research Operations",
        priority="Medium",
        task_type="AI Suggested",
        rationale="Standard practice; not stated in the protocol.",
    ),
    ChecklistItem(
        task="Identify staffing and coverage plan for participant visits",
        category="Research Operations",
        priority="Medium",
        task_type="AI Suggested",
        rationale="Operational consideration; confirm with study team.",
    ),
    ChecklistItem(
        task="Define recruitment and consent materials review path",
        category="Regulatory and Governance",
        priority="Medium",
        task_type="AI Suggested",
        rationale="Common startup step; adapt to local governance.",
    ),
    ChecklistItem(
        task="Agree data quality monitoring cadence with informatics",
        category="Research Informatics",
        priority="Low",
        task_type="AI Suggested",
        rationale="Suggested control; not a protocol requirement.",
    ),
]

CLARIFICATION_TASKS = {
    "planned_enrollment": "Confirm participant enrollment target (not stated in protocol)",
    "study_duration": "Confirm study duration (not stated in protocol)",
    "number_of_sites": "Confirm participating site count (not stated in protocol)",
    "data_sharing": "Clarify data-sharing expectations (ambiguous in protocol)",
}


def _loc(extraction: ProtocolExtraction, field: str, chunks_by_id: dict) -> str:  # type: ignore[valid-type]
    fld: ExtractionField | None = getattr(extraction, field, None)
    if not fld or not fld.source_chunk_ids:
        return ""
    parts = []
    for cid in fld.source_chunk_ids[:2]:
        chunk = chunks_by_id.get(cid)
        if chunk:
            parts.append(f"page {chunk.page}" if chunk.page else chunk.section or "document")
    return ", ".join(dict.fromkeys(parts))


def build_checklist(
    extraction: ProtocolExtraction, chunks_by_id: dict, ai_suggestions: bool = True
) -> list[dict]:  # type: ignore[valid-type]
    items: list[dict] = []

    def add(task: str, category: str, priority: str, task_type: str,
            source: str = "", rationale: str = "") -> None:
        items.append(
            ChecklistItem(
                id=uuid.uuid4().hex[:10],
                task=task,
                category=category,
                priority=priority,
                status="Not Started",
                source_reference=source,
                rationale=rationale,
                task_type=task_type,
                requires_human_review=True,
            ).model_dump()
        )

    for field, (template, priority) in REQUIRED_TASKS.items():
        fld: ExtractionField | None = getattr(extraction, field, None)
        if not fld or fld.value == NOT_SPECIFIED:
            continue
        add(
            template.format(value=fld.value),
            CATEGORY_OF[field],
            priority,
            "Protocol Required",
            source=_loc(extraction, field, chunks_by_id),
            rationale=f"{FIELD_TO_LABEL.get(field, field)} stated in protocol.",
        )

    # missing / ambiguous protocol content
    for field, task in CLARIFICATION_TASKS.items():
        fld = getattr(extraction, field, None)
        if fld and fld.value == NOT_SPECIFIED:
            add(task, "Study Activation", "High", "Needs Clarification",
                rationale="Not specified in the protocol; confirm with the study team.")
    for note in extraction.missing_information[:6]:
        add(f"Clarify: {note}", "Study Activation", "Medium", "Needs Clarification",
            rationale="Flagged as missing during AI extraction; requires human confirmation.")

    # baseline activation items that are always operationally required
    add("Complete site initiation and training", "Study Activation", "High",
        "Protocol Required", rationale="Standard activation step implied by multi-site operation.")
    add("Final readiness review before first enrollment", "Study Activation", "High",
        "Protocol Required", rationale="Governance step; not a substitute for sponsor requirements.")

    if ai_suggestions and extraction.study_type.value != NOT_SPECIFIED:
        for item in AI_SUGGESTED:
            copy = item.model_dump()
            copy["id"] = uuid.uuid4().hex[:10]
            items.append(copy)

    return items


def to_csv(items) -> str:  # type: ignore[valid-type]
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id", "task", "category", "priority", "status", "source_reference",
            "rationale", "task_type", "requires_human_review",
        ],
    )
    writer.writeheader()
    for item in items:
        row = {k: v for k, v in dict(item).items() if k in writer.fieldnames}
        row["requires_human_review"] = int(bool(row.get("requires_human_review", True)))
        writer.writerow(row)
    return buffer.getvalue()
