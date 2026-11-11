# Limitations

Honest constraints of v0.1.0 — each is a known boundary, not a surprise.

## Extraction & AI

- **Ground truth = 3 synthetic documents** authored alongside the protocols. Accuracy numbers do not generalize to real institutional templates.
- **Matcher conservatism. The evaluator counts formatting variants as mismatches in some cases (e.g., "Phase Ib/II" vs phase conventions); treat accuracy as a floor, and read `eval_results/results.json` per-field.
- **Citation support check is lexical** (token overlap); it can pass weak supports and misses semantic ones. `verified` is a signal, not proof.
- **No OCR. Scanned/image-only PDFs are detected and rejected with a clear message; that's a Phase-2 feature.
- **DOCX has no page numbers** — citations cite section/paragraph, never a page (by design, not an oversight).
- Long protocols are truncated to the prompt budget (`~24k` chars extraction, `~9k` per answer); very large documents may need the chunk budget raised.

## Operational

- Single-user, single-process. No authN/authZ beyond network binding — intentional for the demo (see security.md).
- `DOC_RETENTION_DAYS` is config-only; the expiry sweeper is not implemented.
- SQLite is fine for a demo; concurrent multi-user writes would want a real migration path.
- No streaming: responses arrive complete (simpler, verifiable; slower to first token).
- Dockerfiles are standard but **untested on this host** (no docker daemon available during development); CI runs tests/lint/security only.

## Evaluation honesty

Mocked tests prove logic, not model behavior. The live-model integration suite is separate and env-gated. All published metrics come from `scripts/evaluate.py` runs recorded in `eval_results/`; none are hand-written.
