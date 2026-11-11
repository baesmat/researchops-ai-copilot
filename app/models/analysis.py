"""Pydantic domain models: parsed documents, extractions, checklists, answers."""

from __future__ import annotations

from pydantic import BaseModel, Field

NOT_SPECIFIED = "Not specified in the protocol"


# ---------------------------------------------------------------- documents

class DocumentChunk(BaseModel):
    chunk_id: str  # stable: <doc_id>-p<page>-c<index>
    doc_id: str
    text: str
    page: int | None  # None for DOCX (no page numbers invented)
    section: str = ""


class ParsedDocument(BaseModel):
    doc_id: str
    filename: str
    doc_type: str  # pdf | docx
    num_pages: int
    chunks: list[DocumentChunk]
    metadata: dict = Field(default_factory=dict)
    warning: str = ""


# --------------------------------------------------------------- extraction

class ExtractionField(BaseModel):
    value: str = NOT_SPECIFIED
    source_chunk_ids: list[str] = Field(default_factory=list)
    # verified: citation ids exist and chunk text supports the claim (best effort)
    verified: bool = False


class ProtocolExtraction(BaseModel):
    doc_id: str
    # identification
    study_title: ExtractionField = ExtractionField()
    protocol_id: ExtractionField = ExtractionField()
    study_type: ExtractionField = ExtractionField()
    study_phase: ExtractionField = ExtractionField()
    principal_investigator: ExtractionField = ExtractionField()
    sponsor: ExtractionField = ExtractionField()
    # design
    primary_objective: ExtractionField = ExtractionField()
    secondary_objectives: list[ExtractionField] = Field(default_factory=list)
    planned_enrollment: ExtractionField = ExtractionField()
    number_of_sites: ExtractionField = ExtractionField()
    study_duration: ExtractionField = ExtractionField()
    # operational (free-form short values)
    imaging: ExtractionField = ExtractionField()
    laboratory: ExtractionField = ExtractionField()
    biospecimen: ExtractionField = ExtractionField()
    data_storage: ExtractionField = ExtractionField()
    data_sharing: ExtractionField = ExtractionField()
    external_collaboration: ExtractionField = ExtractionField()
    specialized_computing: ExtractionField = ExtractionField()
    software_dependencies: ExtractionField = ExtractionField()
    regulatory: ExtractionField = ExtractionField()
    # gaps the model observed
    missing_information: list[str] = Field(default_factory=list)
    model_name: str = ""
    raw_response: str = ""


# ---------------------------------------------------------------- checklist

class ChecklistItem(BaseModel):
    id: str = ""
    task: str
    category: str
    priority: str = "Medium"  # High | Medium | Low
    status: str = "Not Started"
    source_reference: str = ""
    rationale: str = ""
    # Protocol Required | AI Suggested | Needs Clarification
    task_type: str
    requires_human_review: bool = True


# --------------------------------------------------------------------- QA

class CitedAnswer(BaseModel):
    question: str
    answer: str
    citations: list[str] = Field(default_factory=list)  # chunk ids
    grounded: bool = True  # False => answer flagged as insufficient evidence
    suggestion: str = ""  # clearly-labeled general advice, never protocol fact
    model_name: str = ""
