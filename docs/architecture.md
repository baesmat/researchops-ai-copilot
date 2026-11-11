# Architecture

## Layers

- **UI (`frontend/`)** — Streamlit. Talks to the API over HTTP only; no business logic.
- **API (`app/api/routes.py`)** — Thin REST layer; request validation, orchestration, error mapping (422 validation, 404 unknown, 503 model-unreachable).
- **Services (`app/services/`)** — All domain logic, framework-free:
  - `document_parser` — PDF via PyMuPDF (per-block chunks, page numbers, heading detection, sparse-page/scan detection); DOCX via python-docx (heading/paragraph provenance, **no page numbers invented**). Empty/unreadable inputs raise `ParseError`.
  - `evidence_retriever` — BM25 over chunks. Deterministic by construction; chunk ids `<doc>-p<page>-c<n>` are stable.
  - `llm_client` — Plain OpenAI-compatible HTTP (`/chat/completions`), all config via `LLM_*` env. One controlled JSON repair; typed errors for timeout/shape/parse failures.
  - `protocol_extractor` — prompt assembly (sanitized chunks with ids) → JSON → `extract_from_llm` mapping → per-field citation verification (id exists ∧ lexical support) → `ExtractionField`.
  - `checklist_generator` — rules over verified extractions (`Protocol Required`), missing-info driven (`Needs Clarification`), fixed operational hypotheses (`AI Suggested`). CSV export.
  - `qa_service` — retrieve top-k → answer strictly from excerpts → validate cited ids → `grounded` flag; suggestions separated from facts.
  - `report_generator` — ReportLab PDF; disclaimer, date and app version embedded; no readiness score by design.
- **Security (`app/security/`)** — upload validation (extension allow-list, signature bytes, size cap, NFKC filename sanitization, path stripping) and prompt hygiene (control-char strip, length caps, system/content separation).
- **Storage (`app/storage/database.py`)** — SQLite WAL; `documents`, `analyses` (JSON snapshots), `checklist_items` (user-editable status/priority), `qa_log`. Document deletion cascades to all child tables and removes stored files.

## Data flow (analyze)

```
upload → validate → parse→chunks (id,page,section) → store
analyze: chunks → sanitized excerpt block → LLM JSON
       → field mapping (unknown ids dropped, NOT_SPECIFIED defaults)
       → per-field citation verification
       → checklist build → persistence
ask:     BM25(question) → top-k chunks → grounded prompt → answer+citations
       → citation validation → grounded flag → qa_log
```

## Concurrency & lifecycle

Single process; FastAPI threadpool for requests, synchronous SQLite shared across threads under a re-entrant lock (`check_same_thread=False` deliberately, writes serialized). Parsed documents and BM25 indexes are memoized in-process per document id.

## Deliberate non-features

No vector database, no agent framework, no queues/redis, no microservices. The whole system is one process + one file per concern; the bridge (`scripts/gb10_bridge.py`) is optional host-specific glue and never required by the app itself.
