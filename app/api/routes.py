"""HTTP API: upload, parse, analyze, checklist, qa, reports, deletion."""

from __future__ import annotations

import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import APP_VERSION, AppConfig
from app.models.analysis import ChecklistItem, CitedAnswer, ProtocolExtraction
from app.security.file_validation import ValidationError, validate_upload
from app.storage import database as db
from app.storage.database import LOCK

log = logging.getLogger("researchops.api")


class AnalysisResult(BaseModel):
    doc_id: str
    extraction: ProtocolExtraction
    checklist: list[ChecklistItem]


class QATurn(BaseModel):
    answer: CitedAnswer


def create_app(cfg: AppConfig | None = None) -> FastAPI:  # type: ignore[valid-type]
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="ResearchOps AI Copilot", version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # localhost demo; tightened in production deployment
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # runtime singletons (documents cached in memory for retrieval)
    state = {"cfg": cfg or AppConfig(), "conn": None, "parsed": {}}

    @app.on_event("startup")
    def _startup() -> None:  # type: ignore[valid-type]
        c = state["cfg"]
        c.ensure_dirs()
        state["conn"] = db.connect(c.db_path)
        db.init_db(state["conn"])
        log.info("researchops api v%s ready (%s)", APP_VERSION, c.data_dir)

    @app.on_event("shutdown")
    def _shutdown() -> None:  # type: ignore[valid-type]
        if state["conn"]:
            state["conn"].close()

    def conn():  # type: ignore[valid-type]
        return state["conn"]

    def parsed_doc(doc_id: str):  # type: ignore[valid-type]
        cached = state["parsed"].get(doc_id)
        if cached:
            return cached
        row = db.get_document(conn(), doc_id)
        if row is None:
            raise HTTPException(404, "unknown document")
        path = row["stored_path"]
        try:
            data = open(path, "rb").read()  # noqa: SIM115
        except OSError as exc:
            raise HTTPException(500, f"stored document unreadable: {exc}") from exc
        from app.services.document_parser import parse_document

        parsed = parse_document(data, row["doc_type"], row["filename"])
        state["parsed"][doc_id] = parsed
        return parsed

    def llm():  # type: ignore[valid-type]
        from app.services.llm_client import LLMClient

        return LLMClient(state["cfg"].llm)

    # ------------------------------------------------------------------ core

    @app.get("/healthz")
    def healthz() -> dict:  # type: ignore[valid-type]
        return {"ok": True, "version": APP_VERSION, "llm_configured": state["cfg"].llm.is_configured()}

    @app.post("/api/documents")
    async def upload(file: UploadFile = File(...)):  # type: ignore[valid-type]
        content = await file.read()
        try:
            valid = validate_upload(file.filename or "", content, state["cfg"].max_upload_bytes)
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from exc

        from app.services.document_parser import ParseError, parse_document

        try:
            parsed = parse_document(valid.content, valid.doc_type, valid.filename)
        except ParseError as exc:
            raise HTTPException(422, f"document could not be parsed: {exc}") from exc

        doc_id = parsed.doc_id
        dest = state["cfg"].uploads_dir / f"{doc_id}_{valid.filename}"
        dest.write_bytes(content)

        db.add_document(conn(), doc_id, valid.filename, valid.doc_type, str(dest))
        db.update_document(
            conn(), doc_id, status="parsed", num_pages=parsed.num_pages,
            num_chunks=len(parsed.chunks), error=parsed.warning,
        )
        state["parsed"][doc_id] = parsed
        return {
            "doc_id": doc_id,
            "filename": valid.filename,
            doc_type_key: parsed.doc_type,
            "num_pages": parsed.num_pages,
            "num_chunks": len(parsed.chunks),
            "warning": parsed.warning,
        }

    @app.get("/api/documents")
    def list_documents() -> list:  # type: ignore[valid-type]
        return [dict(r) for r in db.list_documents(conn())]

    @app.get("/api/documents/{doc_id}")
    def get_document(doc_id: str) -> dict:  # type: ignore[valid-type]
        row = db.get_document(conn(), doc_id)
        if row is None:
            raise HTTPException(404, "unknown document")
        return dict(row)

    @app.get("/api/documents/{doc_id}/preview")
    def preview(doc_id: str, max_chunks: int = 12) -> dict:  # type: ignore[valid-type]
        parsed = parsed_doc(doc_id)
        chunks = [
            {"chunk_id": c.chunk_id, "page": c.page, "section": c.section, "text": c.text[:400]}
            for c in parsed.chunks[:max_chunks]
        ]
        return {"doc_id": doc_id, "filename": parsed.filename, "chunks": chunks}

    @app.delete("/api/documents/{doc_id}")
    def delete_document(doc_id: str) -> dict:  # type: ignore[valid-type]
        row = db.delete_document(conn(), doc_id)
        if row is None:
            raise HTTPException(404, "unknown document")
        state["parsed"].pop(doc_id, None)
        deleted_files = []
        path = row["stored_path"]
        try:
            import os

            if os.path.exists(path):
                os.unlink(path)
                deleted_files.append(path)
        except OSError as exc:
            log.warning("cleanup failed for %s: %s", path, exc)
        return {"deleted": doc_id, "files_removed": deleted_files}

    # ------------------------------------------------------------- analysis

    @app.post("/api/documents/{doc_id}/analyze")
    async def analyze(doc_id: str) -> dict:  # type: ignore[valid-type]
        from app.services.checklist_generator import build_checklist
        from app.services.protocol_extractor import extract_protocol

        parsed = parsed_doc(doc_id)
        try:
            extraction = await extract_protocol(parsed, llm())
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

        chunks_by_id = {c.chunk_id: c for c in parsed.chunks}
        items = build_checklist(extraction, chunks_by_id)
        with LOCK:
            db.save_analysis(conn(), doc_id, extraction.model_dump_json())
            db.replace_checklist(conn(), doc_id, items)
            db.update_document(conn(), doc_id, status="analyzed")
        return AnalysisResult(doc_id=doc_id, extraction=extraction,
                              checklist=[ChecklistItem(**i) for i in items]).model_dump()

    @app.get("/api/documents/{doc_id}/analysis")
    def get_analysis(doc_id: str) -> dict:  # type: ignore[valid-type]
        row = db.latest_analysis(conn(), doc_id)
        if row is None:
            raise HTTPException(404, "no analysis; run POST /api/documents/{id}/analyze")
        items = [dict(r) | {"requires_human_review": bool(r["requires_human_review"])}
                 for r in db.list_checklist(conn(), doc_id)]
        return {
            "doc_id": doc_id,
            "extraction": __import__("json").loads(row["extraction_json"]),
            "checklist": [ChecklistItem(**i).model_dump() for i in items],
        }

    @app.get("/api/documents/{doc_id}/checklist.csv")
    def checklist_csv(doc_id: str) -> Response:  # type: ignore[valid-type]
        from app.services.checklist_generator import to_csv

        rows = db.list_checklist(conn(), doc_id)
        if not rows:
            raise HTTPException(404, "no checklist for document")
        return Response(
            content=to_csv([dict(r) for r in rows]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="checklist_{doc_id}.csv"'},
        )

    @app.patch("/api/checklist/{item_id}")
    def patch_item(item_id: str, status: str = "", priority: str = "") -> dict:  # type: ignore[valid-type]
        fields = {}
        if status:
            if status not in {"Not Started", "In Progress", "Done", "Blocked"}:
                raise HTTPException(422, "invalid status")
            fields["status"] = status
        if priority:
            if priority not in {"High", "Medium", "Low"}:
                raise HTTPException(422, "invalid priority")
            fields["priority"] = priority
        row = db.update_checklist_item(conn(), item_id, **fields)
        if row is None:
            raise HTTPException(404, "unknown checklist item")
        return dict(row) | {"requires_human_review": bool(row["requires_human_review"])}

    # ------------------------------------------------------------------- qa

    @app.post("/api/documents/{doc_id}/ask")
    async def ask(doc_id: str, payload: dict) -> dict:  # type: ignore[valid-type]
        from app.services.evidence_retriever import BM25Index
        from app.services.qa_service import answer_question

        question = str(payload.get("question", "")).strip()
        if not question:
            raise HTTPException(422, "question required")
        parsed = parsed_doc(doc_id)
        index = state["parsed"].get(f"idx:{doc_id}")
        if index is None or getattr(index, "_doc", None) is not parsed:
            index = BM25Index(parsed.chunks)
            state["parsed"][f"idx:{doc_id}"] = index
        try:
            result: CitedAnswer = answer_question(parsed, index, question, llm())
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        with LOCK:
            db.log_qa(conn(), doc_id, result.question, result.answer,
                      result.citations, result.grounded)
        return result.model_dump()

    # -------------------------------------------------------------- reports

    @app.get("/api/documents/{doc_id}/report.pdf")
    def report(doc_id: str) -> Response:  # type: ignore[valid-type]
        import json

        from app.services.report_generator import build_report

        row = db.latest_analysis(conn(), doc_id)
        if row is None:
            raise HTTPException(404, "no analysis; run analyze first")
        doc_row = db.get_document(conn(), doc_id)
        extraction = ProtocolExtraction(**json.loads(row["extraction_json"]))
        checklist = [
            dict(r) | {"requires_human_review": bool(r["requires_human_review"])}
            for r in db.list_checklist(conn(), doc_id)
        ]
        pdf = build_report(extraction, checklist, doc_row["filename"])
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="study_readiness_{doc_id}.pdf"'},
        )

    # --------------------------------------------------------------- stats

    @app.get("/api/stats")
    def stats() -> dict:  # type: ignore[valid-type]
        return db.stats(conn())

    doc_type_key = "doc_type"  # used in upload response above
    return app
