"""Executive study-readiness report (PDF via reportlab).

Summarizes observed gaps and review items. No authoritative readiness score is
computed — the report is a structured brief for humans, with a standing
AI-generated disclaimer.
"""

from __future__ import annotations

import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import APP_VERSION
from app.models.analysis import NOT_SPECIFIED, ProtocolExtraction
from app.services.protocol_extractor import FIELD_TO_LABEL

NAVY = colors.HexColor("#1B2A4A")
TEAL = colors.HexColor("#2A7F8F")
GRAY = colors.HexColor("#5A6472")

DISCLAIMER = (
    "AI-generated demonstration report. Requires review and validation by qualified research "
    "personnel. Not an institutional approval or clinical decision."
)


def _styles() -> dict:  # type: ignore[valid-type]
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Title"], fontSize=17, textColor=NAVY, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, textColor=NAVY,
                             spaceBefore=10, spaceAfter=3),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=12.5),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=7.5,
                                textColor=GRAY, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8, leading=10),
    }


def _kv_table(rows: list[tuple[str, str]], style) -> Table:  # type: ignore[valid-type]
    data = [[Paragraph(f"<b>{k}</b>", style["cell"]), Paragraph(v, style["cell"])] for k, v in rows]
    table = Table(data, colWidths=[1.9 * inch, 4.6 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D2D9")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF3F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def build_report(
    extraction: ProtocolExtraction,
    checklist: list[dict],
    doc_filename: str,
) -> bytes:  # type: ignore[valid-type]
    import io

    s = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Study Readiness Report",
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story: list = []
    today = datetime.date.today().isoformat()

    story.append(Paragraph("Study Readiness Report", s["h1"]))
    story.append(Paragraph("ResearchOps AI Copilot — demonstration output", s["small"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL))
    story.append(Spacer(1, 6))

    # 1 overview
    story.append(Paragraph("1. Study Overview", s["h2"]))
    story.append(
        _kv_table(
            [
                ("Document", doc_filename),
                ("Protocol ID", extraction.protocol_id.value),
                ("Study title", extraction.study_title.value),
                ("Study type / phase",
                 f"{extraction.study_type.value} / {extraction.study_phase.value}"),
                ("Principal investigator", extraction.principal_investigator.value),
                ("Sponsor", extraction.sponsor.value),
                ("Planned enrollment", extraction.planned_enrollment.value),
                ("Sites / duration",
                 f"{extraction.number_of_sites.value} / {extraction.study_duration.value}"),
            ],
            s,
        )
    )

    # 2 objectives
    story.append(Paragraph("2. Research Objectives", s["h2"]))
    story.append(Paragraph(f"Primary: {extraction.primary_objective.value}", s["body"]))
    for i, sec in enumerate(extraction.secondary_objectives[:5], 1):
        story.append(Paragraph(f"Secondary {i}: {sec.value}", s["body"]))

    # 3-5 operational / informatics / tech dependencies
    operational = ["regulatory", "imaging", "laboratory", "biospecimen"]
    informatics = ["data_storage", "data_sharing", "external_collaboration"]
    technical = ["specialized_computing", "software_dependencies"]

    def section(num: int, title: str, keys: list[str]) -> None:  # type: ignore[valid-type]
        story.append(Paragraph(f"{num}. {title}", s["h2"]))
        rows = []
        for key in keys:
            fld = getattr(extraction, key)
            label = FIELD_TO_LABEL[key]
            note = "" if fld.verified else " <i>(citation unverified)</i>" if fld.source_chunk_ids else ""
            rows.append((label, f"{fld.value}{note}"))
        story.append(_kv_table(rows, s))

    section(3, "Operational Requirements", operational)
    section(4, "Research Informatics Requirements", informatics)
    section(5, "Technology Dependencies", technical)

    # 6 missing information
    story.append(Paragraph("6. Missing Information", s["h2"]))
    missing = [m for m in extraction.missing_information if m.strip()]
    not_specified = [
        FIELD_TO_LABEL[k] for k in FIELD_TO_LABEL
        if getattr(extraction, k).value == NOT_SPECIFIED
    ]
    if missing or not_specified:
        for m in missing:
            story.append(Paragraph(f"• {m}", s["body"]))
        if not_specified:
            story.append(Paragraph(
                "Not specified in the protocol: " + ", ".join(not_specified), s["body"]))
    else:
        story.append(Paragraph("No missing information observed by the extraction pass.", s["body"]))

    # 7 checklist summary
    story.append(Paragraph("7. Suggested Startup Checklist (summary)", s["h2"]))
    by_type: dict[str, int] = {}
    for item in checklist:
        by_type[item["task_type"]] = by_type.get(item["task_type"], 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items())) or "none"
    story.append(Paragraph(f"Checklist contains {len(checklist)} items: {summary}.", s["body"]))
    high = [i for i in checklist if i["priority"] == "High"][:12]
    for item in high:
        tag = " [needs clarification]" if item["task_type"] == "Needs Clarification" else ""
        story.append(Paragraph(f"• ({item['category']}) {item['task']}{tag}", s["body"]))

    # 8 risks
    story.append(Paragraph("8. Risks and Considerations", s["h2"]))
    story.append(Paragraph(
        "Observed gaps and unverified extractions are listed above; they are risks to be "
        "confirmed, not established findings. AI-suggested items are operational hypotheses.",
        s["body"],
    ))

    # 9 source references
    story.append(Paragraph("9. Source References", s["h2"]))
    refs = set()
    for key in FIELD_TO_LABEL:
        fld = getattr(extraction, key)
        for cid in fld.source_chunk_ids:
            refs.add(f"{cid} — {FIELD_TO_LABEL[key]}")
    for ref in sorted(refs)[:24]:
        story.append(Paragraph(f"• {ref}", s["body"]))
    if not refs:
        story.append(Paragraph("No citations recorded.", s["body"]))

    # 10 human review
    story.append(Paragraph("10. Human Review Requirements", s["h2"]))
    story.append(Paragraph(
        "Every item in this report requires confirmation by the study team and research "
        "informatics. Items marked as needing clarification must be resolved before startup. "
        "AI-suggested items require explicit approval before being treated as commitments.",
        s["body"],
    ))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Paragraph(f"{DISCLAIMER} Generated {today} — app v{APP_VERSION}.", s["small"]))

    doc.build(story)
    return buffer.getvalue()
