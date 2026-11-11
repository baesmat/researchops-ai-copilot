#!/usr/bin/env python3
"""Evaluate extraction quality against the synthetic ground truth.

Requires a configured model endpoint (LLM_* env). Writes:
  eval_results/results.json   machine-readable
  eval_results/summary.md     human-readable
Only measured values are reported.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config import LLMConfig  # noqa: E402
from app.models.analysis import NOT_SPECIFIED, ProtocolExtraction  # noqa: E402
from app.services.document_parser import parse_document  # noqa: E402
from app.services.llm_client import LLMClient  # noqa: E402
from app.services.protocol_extractor import extract_protocol  # noqa: E402

FIELDS = [
    "protocol_id", "study_title", "study_type", "study_phase", "principal_investigator",
    "sponsor", "planned_enrollment", "number_of_sites", "study_duration",
]


def _norm(s: str) -> str:  # type: ignore[valid-type]
    return re.sub(r"\s+", " ", s).strip().lower()


def _matches(predicted: str, truth: str | None) -> bool:  # type: ignore[valid-type]
    if truth is None:
        return predicted.strip() == NOT_SPECIFIED or predicted.strip() == ""
    if predicted.strip() in ("", NOT_SPECIFIED):
        return False
    a, b = _norm(predicted), _norm(truth)
    return a in b or b in a or a[:25] == b[:25]


async def evaluate(data_dir: pathlib.Path, llm: LLMClient) -> dict:  # type: ignore[valid-type]
    per_doc = []
    totals = {
        "fields_total": 0, "fields_correct": 0,
        "citations_total": 0, "citations_valid": 0,
        "structured_ok": 0, "structured_attempts": 0,
        "latency_s": [],
    }
    for gt_path in sorted(data_dir.glob("*.ground_truth.json")):
        gt = json.loads(gt_path.read_text())
        pdf_path = data_dir / gt["source_pdf"]
        t0 = time.time()
        parsed = parse_document(pdf_path.read_bytes(), "pdf", pdf_path.name)
        totals["structured_attempts"] += 1
        try:
            extraction: ProtocolExtraction = await extract_protocol(parsed, llm)
            totals["structured_ok"] += 1
        except RuntimeError as exc:
            per_doc.append({
                "doc": gt["source_pdf"], "error": str(exc)[:200],
            })
            continue
        elapsed = time.time() - t0
        totals["latency_s"].append(round(elapsed, 1))

        chunks_by_id = {c.chunk_id: c for c in parsed.chunks}
        doc_result: dict = {"doc": gt["source_pdf"], "fields": {}, "citation_issues": []}
        for field in FIELDS:
            fld = getattr(extraction, field)
            truth = gt.get(field)
            ok = _matches(fld.value, truth)
            totals["fields_total"] += 1
            totals["fields_correct"] += int(ok)
            doc_result["fields"][field] = {
                "predicted": fld.value[:120], "expected": truth, "match": ok,
            }
            for cid in fld.source_chunk_ids:
                totals["citations_total"] += 1
                if cid in chunks_by_id:
                    totals["citations_valid"] += 1
                else:
                    doc_result["citation_issues"].append(f"unknown id {cid}")
        per_doc.append(doc_result)

    n = max(len(totals["latency_s"]), 1)
    return {
        "field_accuracy": round(totals["fields_correct"] / max(totals["fields_total"], 1), 3),
        "citation_validity": round(totals["citations_valid"] / max(totals["citations_total"], 1), 3)
        if totals["citations_total"] else None,
        "structured_output_success": round(
            totals["structured_ok"] / max(totals["structured_attempts"], 1), 3
        ),
        "mean_latency_s": round(sum(totals["latency_s"]) / n, 1),
        "documents": len(totals["latency_s"]),
        "model": llm.cfg.model,
        "endpoint": llm.cfg.base_url,
        "per_document": per_doc,
        "totals": {k: v for k, v in totals.items() if k != "latency_s"},
    }


def write_summary(results: dict, path: pathlib.Path) -> None:  # type: ignore[valid-type]
    lines = [
        "# Extraction Evaluation — measured results",
        "",
        f"- Model: `{results['model']}` via `{results['endpoint']}`",
        f"- Documents evaluated: {results['documents']} (synthetic ground-truth set)",
        f"- Field accuracy: **{results['field_accuracy']:.1%}**",
        f"- Citation validity: {results['citation_validity']}",
        f"- Structured-output success: **{results['structured_output_success']:.1%}**",
        f"- Mean latency per document: {results['mean_latency_s']} s",
        "",
        "Limitations: three synthetic documents authored alongside the ground truth; ",
        "results measure extraction formatting as well as comprehension, and do not ",
        "generalize to real protocols.",
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/synthetic")
    parser.add_argument("--out-dir", default="eval_results")
    args = parser.parse_args()
    import asyncio

    llm = LLMClient(LLMConfig())
    if not llm.configured():
        print("LLM not configured: set LLM_BASE_URL / LLM_MODEL (and LLM_API_KEY if needed)")
        raise SystemExit(2)

    results = asyncio.run(evaluate(pathlib.Path(args.data_dir), llm))
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    write_summary(results, out / "summary.md")
    print(json.dumps({k: v for k, v in results.items() if k != "per_document"}, indent=2))


if __name__ == "__main__":
    main()
