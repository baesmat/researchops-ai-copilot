# Development Progress Log

Living record of significant decisions and outstanding issues. Newest last.

## 2026-11-10 — initial build (v0.1.0)

**Completed**
- Environment survey per spec §2 (Debian 13 aarch64, Python 3.13.5, 15 GB RAM; no docker daemon on host — noted).
- Full app skeleton per §5; config/env; pydantic models; security modules; sqlite layer.
- Synthetic protocol generator (`scripts/generate_protocols.py`) → 3 PDFs + ground truth; **ground truth programmatically verified against rendered PDF text** (all non-convention fields traceable).
- Parser, BM25 retriever, llm client, extractor, checklist, QA, report generator; REST API; Streamlit UI.
- 32 mocked tests green; ruff clean; bandit clean (B608 skipped with justification).
- **Live-model validation through the app**: bridge (`scripts/gb10_bridge.py`, localhost:8893) → hermes CLI route → GLM-5.3-Flash-EXL3.
  - Integration test PASSED (analyze → grounded QA → PDF report).
  - Full §27 workflow on all 3 synthetic protocols: extractions match ground truth incl. deliberate missing/contradictory cases; 5/5 lung Q&As grounded with valid citations; report 3-page PDF; CSV export; deletion cascade verified (0 orphan rows, files removed).
- Evaluation (measured): field accuracy **0.815**, citation validity **1.0**, structured-output success **1.0**, mean latency 31.7 s/document → `eval_results/`.

**Key decisions**
- Deterministic BM25 + stable chunk ids instead of embeddings: citation *validation* requires determinism; zero heavy deps.
- Duration/verification from data, not hope: citation support = id existence ∧ lexical overlap; `grounded=False` path for unsupported answers.
- Bridge kept out of the app core: app speaks plain OpenAI-compatible HTTP; the bridge is host glue (hermes CLI route works where direct CF Access from plain clients 403s — root cause not fully diagnosed; hermes's own client path verified working).
- No docker daemon locally: compose files written to spec, validated by construction + CI; runtime compose test outstanding.

**Known issues / outstanding**
- Protocol PDFs are 2–3 pages (spec suggests 5–8): content density adequate for the pipeline but below the letter of §6; enrich before final publish if time allows.
- `DOC_RETENTION_DAYS` parsed but no expiry sweeper yet.
- Streamlit E2E click-through + screenshots pending (chromium on this host needs library shim; attempt queued).
- Docker runtime validation pending (no local daemon).
- Evaluator counts some formatting variants as misses (documented in limitations); accuracy is a floor.
- `on_event` deprecation warnings from FastAPI — cosmetic; migrate to lifespan later.

## Status vs completion criteria (§32)

| Criterion | State |
|---|---|
| Application starts | ✅ verified (uvicorn boot + healthz) |
| All 3 synthetic protocols analyze | ✅ live-model verified |
| Structured extraction w/ configured model | ✅ |
| Checklist generation | ✅ |
| Q&A with traceable citations | ✅ (validation + UI display) |
| Reports downloadable | ✅ (3-page PDF, disclaimer embedded) |
| Deletion works | ✅ (cascade + files, tested) |
| Automated tests pass | ✅ 32/32 mocked; 1/1 live integration |
| Evaluation script produces real results | ✅ `eval_results/` |
| Docker deployment works | ⚠️ files complete; runtime untested (no daemon here) |
| README accurate | ✅ written against implemented behavior |
| Screenshots | ⏳ pending browser capture |
| No credentials committed | ✅ env-only; verify pass before push pending |
| Publication-ready | ⏳ final secret sweep + your approval (§26) |
