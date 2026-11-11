"""Streamlit UI. Run: streamlit run frontend/streamlit_app.py

Requires the API (app.main) running; API base URL via API_BASE env
(default http://127.0.0.1:8410).
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8410").rstrip("/")

st.set_page_config(page_title="ResearchOps AI Copilot", page_icon="🧬", layout="wide")

CSS = """
<style>
:root{--navy:#1B2A4A;--teal:#2A7F8F;--gray:#5A6472;}
#MainMenu{visibility:hidden;}
footer{visibility:hidden;}
.block-container{padding-top:1.6rem;max-width:1200px;}
h1{color:var(--navy);letter-spacing:-.02em;}
h2,h3{color:var(--navy);}
.stTabs [data-baseweb="tab-list]{gap:6px;}
.stTabs [data-baseweb="tab"]{padding:8px 18px;border-radius:8px 8px 0 0;}
.stTabs [aria-selected="true"]{background:#EEF3F6;}
.disclaimer{color:var(--gray);font-size:.78rem;border-top:1px solid #D9E0E5;
padding-top:.5rem;margin-top:2rem;}
.badge{display:inline-block;padding:1px 9px;border-radius:99px;font-size:.72rem;
border:1px solid var(--teal);color:var(--navy);margin-right:4px;}
.kpi{font-size:2rem;font-weight:700;color:var(--teal);}
.kpi-label{font-size:.8rem;color:var(--gray);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(ttl=5)
def api_get(path: str, ok=(200,)):
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=15)
        return r.json() if r.status_code in ok or r.status_code == 200 else {"error": r.text}
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


def api_post(path: str, **kwargs):
    try:
        r = httpx.post(f"{API_BASE}{path}", timeout=180, **kwargs)
        return r.json() if r.status_code < 300 else {"error": r.text, "status": r.status_code}
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


def header(title: str, subtitle: str = "") -> None:  # type: ignore[valid-type]
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)


def disclaimer() -> None:  # type: ignore[valid-type]
    st.markdown(
        '<div class="disclaimer">Independent demonstration using synthetic data only. '
        "AI output requires review by qualified research personnel and is not an "
        "institutional approval, clinical decision, or HIPAA-compliant process.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- session ui

def sidebar() -> str | None:  # type: ignore[valid-type]
    with st.sidebar:
        st.markdown("## 🧬 ResearchOps AI Copilot")
        st.caption("Synthetic-data demonstration")
        uploaded = st.file_uploader("Upload protocol (PDF / DOCX, ≤15 MB)", type=["pdf", "docx"])
        if uploaded and st.button("Ingest document", type="primary"):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/pdf")}
            result = api_post("/api/documents", files=files)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(
                    f"Ingested: {result['num_chunks']} sections"
                    + (f" — {result['warning']}" if result.get("warning") else "")
                )
                st.cache_data.clear()
                st.rerun()

        docs = api_get("/api/documents")
        options = {}
        if isinstance(docs, list):
            options = {f"{d['filename']} ({d['status']})": d["id"] for d in docs}
        selected = st.selectbox("Active document", ["<none>"] + list(options)) if options else "<none>"
        doc_id = options.get(selected) if options else None

        if doc_id and st.button("🗑 Remove document"):
            try:
                httpx.delete(f"{API_BASE}/api/documents/{doc_id}", timeout=30)
                st.cache_data.clear()
                st.rerun()
            except httpx.HTTPError as exc:
                st.error(str(exc))

        health = api_get("/healthz")
        llm_ok = health.get("llm_configured") if isinstance(health, dict) else None
        st.caption(f"Model endpoint: {'configured ✔' if llm_ok else 'NOT configured ✘'}")
        st.caption(f"API: {API_BASE}")
    return doc_id


def kpi_row(stats: dict) -> None:  # type: ignore[valid-type]
    cols = st.columns(5)
    cells = [
        (stats.get("documents", 0), "protocols ingested"),
        (stats.get("analyzed", 0), "protocols analyzed"),
        (stats.get("checklist_items", 0), "checklist items"),
        (stats.get("needs_clarification", 0), "need clarification"),
        (len(stats.get("recent") or []), "recent documents"),
    ]
    for col, (value, label) in zip(cols, cells, strict=True):
        col.markdown(f'<div class="kpi">{value}</div>'
                     f'<div class="kpi-label">{label}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------- pages

def page_dashboard() -> None:  # type: ignore[valid-type]
    header("Program Dashboard", "Ingestion and analysis status across the demonstration workspace.")
    stats = api_get("/api/stats")
    if "error" in stats:
        st.error(stats["error"])
        return  # type: ignore[func-returns-value]
    kpi_row(stats)
    st.divider()
    st.markdown("#### Recent activity")
    for row in stats.get("recent") or []:
        st.markdown(f"- `{row['id']}` **{row['filename']}** — {row['status']} ({row['ts']})")
    if not stats.get("recent"):
        st.info("No documents yet — upload a synthetic protocol from the sidebar.")


def render_field(label: str, fld: dict) -> None:  # type: ignore[valid-type]
    cites = ", ".join(fld.get("source_chunk_ids") or [])
    check = "✅" if fld.get("verified") else ("🔎" if cites else "•")
    st.markdown(
        f"**{label}:** {fld.get('value')} &nbsp;{check}\n\n"
        f"<span style='color:#5A6472;font-size:.75rem'>source: {cites or '—'}</span>",
        unsafe_allow_html=True,
    )


def page_analysis(doc_id: str | None) -> None:  # type: ignore[valid-type]
    header("Protocol Analysis", "Structured extraction with evidence citations.")
    if not doc_id:
        st.info("Select or ingest a document first.")
        return  # type: ignore[func-returns-value]

    if st.button("Run AI extraction", type="primary"):
        with st.spinner("Analyzing with the configured model…"):
            result = api_post(f"/api/documents/{doc_id}/analyze")
        if "error" in result:
            st.error(result["error"])
        else:
            st.cache_data.clear()
            st.success("Analysis complete.")

    analysis = api_get(f"/api/documents/{doc_id}/analysis")
    if "error" in analysis:
        st.info("No analysis yet — run the extraction above.")
        return  # type: ignore[func-returns-value]

    ex = analysis["extraction"]
    left, right = st.columns([2, 3])
    with left:
        st.markdown("#### Study identification")
        for key, label in [
            ("study_title", "Title"), ("protocol_id", "Protocol ID"), ("study_type", "Type"),
            ("study_phase", "Phase"), ("principal_investigator", "PI"),
        ]:
            render_field(label, ex.get(key, {}))
        render_field("Sponsor", ex.get("sponsor", {}))
        st.markdown("#### Design")
        for key in ("planned_enrollment", "number_of_sites", "study_duration"):
            render_field(key.replace("_", " ").title(), ex.get(key, {}))
    with right:
        st.markdown("#### Operational requirements")
        for key in ("regulatory", "imaging", "laboratory", "biospecimen", "data_storage",
                    "data_sharing", "external_collaboration", "specialized_computing",
                    "software_dependencies"):
            render_field(key.replace("_", " ").title(), ex.get(key, {}))

    st.divider()
    st.markdown("#### Missing information")
    for note in ex.get("missing_information") or []:
        st.markdown(f"- {note}")
    st.markdown("##### Secondary objectives")
    for i, sec in enumerate(ex.get("secondary_objectives") or [], 1):
        render_field(f"Objective {i}", sec)


def page_checklist(doc_id: str | None) -> None:  # type: ignore[valid-type]
    header("Study Startup Checklist", "Editable; every item carries its evidence and review flag.")
    if not doc_id:
        st.info("Select a document.")
        return  # type: ignore[func-returns-value]
    analysis = api_get(f"/api/documents/{doc_id}/analysis")
    if "error" in analysis:
        st.info("Run an analysis first.")
        return  # type: ignore[func-returns-value]

    items = analysis["checklist"]
    type_filter = st.multiselect(
        "Task type", ["Protocol Required", "AI Suggested", "Needs Clarification"],
        default=["Protocol Required", "Needs Clarification", "AI Suggested"],
    )
    for item in items:
        if item["task_type"] not in type_filter:
            continue
        with st.container(border=True):
            cols = st.columns([4, 1.2, 1.2, 1.4])
            cols[0].markdown(
                f"**{item['task']}**<br><span style='font-size:.72rem;color:#5A6472'>"
                f"{item['category']} · {item['task_type']} · source: "
                f"{item['source_reference'] or '—'}</span>",
                unsafe_allow_html=True,
            )
            status = cols[1].selectbox(
                "status", ["Not Started", "In Progress", "Done", "Blocked"],
                index=["Not Started", "In Progress", "Done", "Blocked"].index(item["status"]),
                key=f"st-{item['id']}",
            )
            priority = cols[2].selectbox(
                "priority", ["High", "Medium", "Low"],
                index=["High", "Medium", "Low"].index(item["priority"]),
                key=f"pr-{item['id']}",
            )
            if cols[3].button("Save", key=f"sv-{item['id']}"):
                try:
                    httpx.patch(
                        f"{API_BASE}/api/checklist/{item['id']}",
                        params={"status": status, "priority": priority}, timeout=15,
                    )
                    st.cache_data.clear()
                    st.rerun()
                except httpx.HTTPError as exc:
                    st.error(str(exc))
            if item["rationale"]:
                cols[0].caption(item["rationale"])

    csv_bytes = httpx.get(f"{API_BASE}/api/documents/{doc_id}/checklist.csv", timeout=15).content
    st.download_button("⬇ Export checklist (CSV)", csv_bytes,
                       file_name=f"checklist_{doc_id}.csv", mime="text/csv")


def page_ask(doc_id: str | None) -> None:  # type: ignore[valid-type]
    header("Ask the Protocol", "Retrieval-grounded answers; citations are validated chunk ids.")
    if not doc_id:
        st.info("Select a document.")
        return  # type: ignore[func-returns-value]

    for turn in st.session_state.get("history", []):
        with st.chat_message("user" if turn["role"] == "user" else "assistant"):
            st.markdown(turn["content"])

    question = st.chat_input("Ask about the protocol…")
    examples = [
        "What is the planned enrollment?",
        "Does this study require specialized imaging?",
        "What data management requirements are described?",
        "What is missing before study startup?",
    ]
    cols = st.columns(len(examples))
    for col, example in zip(cols, examples, strict=True):
        if col.button(example[:28] + "…", key=f"ex-{example[:12]}"):
            question = example  # noqa: F841

    if question and not getattr(question, "startswith", lambda _: False)("ex-"):
        st.session_state.setdefault("history", []).append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.spinner("Retrieving passages and querying the model…"):
            result = api_post(f"/api/documents/{doc_id}/ask", json={"question": question})
        if "error" in result:
            st.error(result["error"])
        return  # type: ignore[func-returns-value]
        answer_md = result["answer"]
        cites = ", ".join(result.get("citations") or [])
        flag = "✅ grounded" if result.get("grounded") else "⚠️ insufficient evidence in document"
        body = f"{answer_md}\n\n**Citations:** {cites or '—'} · _{flag}_"
        if result.get("suggestion"):
            body += f"\n\n> 💡 *General suggestion (not from the protocol):* {result['suggestion']}"
        st.session_state["history"].append({"role": "assistant", "content": body})
        with st.chat_message("assistant"):
            st.markdown(body, unsafe_allow_html=True)



def page_reports(doc_id: str | None) -> None:  # type: ignore[valid-type]
    header("Executive Study Readiness Report", "Generated PDF; disclaimer embedded.")
    if not doc_id:
        st.info("Select an analyzed document.")
        return  # type: ignore[func-returns-value]
    analysis = api_get(f"/api/documents/{doc_id}/analysis")
    if "error" in analysis:
        st.info("An analysis is required before a report can be generated.")
        return  # type: ignore[func-returns-value]

    st.markdown("The report compiles: overview, objectives, operational and informatics "
                "requirements, technology dependencies, missing information, checklist summary, "
                "risks, source references, and human-review requirements.")
    if st.button("Generate report", type="primary"):
        with st.spinner("Rendering PDF…"):
            pdf = httpx.get(f"{API_BASE}/api/documents/{doc_id}/report.pdf", timeout=60)
        if pdf.status_code != 200:
            st.error(pdf.text)
        return  # type: ignore[func-returns-value]
        st.download_button("⬇ Download study readiness report", pdf.content,
                           file_name=f"study_readiness_{doc_id}.pdf", mime="application/pdf")
        st.success("Report ready — see download button.")


def main() -> None:  # type: ignore[valid-type]
    st.markdown(
        "<h1 style='margin-bottom:0'>🧬 ResearchOps AI Copilot</h1>"
        "<p style='color:#5A6472;margin-top:0'>Protocol intelligence for research "
        "administrators and research informatics — synthetic-data demonstration.</p>",
        unsafe_allow_html=True,
    )
    doc_id = sidebar()
    dashboard, analysis, checklist, ask, reports = st.tabs(
        ["Dashboard", "Protocol Analysis", "Startup Checklist", "Ask the Protocol", "Reports"]
    )
    with dashboard:
        page_dashboard()
    with analysis:
        page_analysis(doc_id)
    with checklist:
        page_checklist(doc_id)
    with ask:
        page_ask(doc_id)
    with reports:
        page_reports(doc_id)
    disclaimer()


if __name__ == "__main__":
    main()
