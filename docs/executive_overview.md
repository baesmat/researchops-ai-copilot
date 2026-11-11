# Executive Overview — ResearchOps AI Copilot

*Two pages, for a nontechnical leadership audience. Demonstration context: all data synthetic; independent project, no institutional affiliation.*

## The problem

When a new clinical research protocol arrives, its burden lands across administrators, regulatory staff, research informatics, and the study team. Each group must mine the same document for different facts — approvals, imaging, data storage, specimen handling, computing — and reconcile them with local infrastructure. The work is slow, error-prone at the seams between teams, and repeats for every amendment and every new study. The cost is invisible until a startup slips or a requirement is discovered late.

## The proposed solution

An assistive workspace, not an autopilot: staff upload a protocol; the system returns **structured study facts with citations**, a **study-startup checklist** that separates what the protocol demands from what the AI merely suggests, plain-language **answers grounded in the document**, and an **executive readiness brief** that names the gaps instead of hiding them. Every claim can be traced to the passage it came from; anything the document does not say is labeled as missing.

## Potential institutional value (hypotheses to validate, not measured claims)

- Earlier visibility of operational and informatics requirements during startup planning.
- Fewer back-and-forth rounds between research operations and IT by attaching evidence to each question.
- A consistent, auditable first-pass review, useful for onboarding staff and for amendments.
- A reusable pattern for other document-heavy research workflows (consent templates, data use agreements).

These benefits require measurement in a controlled pilot before any productivity claim is made.

## Research informatics relevance

The demonstration is built around the questions informatics actually receives: data storage and sharing, specialized computing, software dependencies, integrations, and cross-site coordination. Its evidence-citation design also makes AI output *checkable* — a prerequisite for trust in a research environment.

## Security & governance posture

Runs locally, holds no PHI (synthetic data only), sends documents only to an institutionally-approved endpoint, and treats uploaded documents as untrusted data. It makes **no HIPAA compliance claim**. Production adoption requires the controls in `docs/security.md`: SSO, role-based access, audit logging, encryption, security review, and validated model hosting.

## Operational requirements to pilot

A small container host, an approved model endpoint, a review workflow owner, and agreement on where AI-drafted checklists live in the existing startup process. The demo itself needs no cloud services and no patient data.

## Implementation roadmap (go/no-go at each gate)

1. **Discovery** — stakeholders, protocol corpus, constraints. *Gate:* agreed pilot scope + success measures.
2. **Controlled pilot** — synthetic/de-identified protocols, 2–3 teams. *Gate:* staff-rated usefulness and citation spot-check accuracy above the agreed bar.
3. **Validation** — measured accuracy against institutional protocols, security review, workflow fit. *Gate:* documented accuracy + security sign-off.
4. **Integration** — EDC/CTMS touchpoints, SSO, retention. *Gate:* integration test plan executed.
5. **Operationalization** — ownership, monitoring, support, lifecycle. *Gate:* named service owner and support path.

## Risks

Over-trust in AI output (mitigated by forced citations, review flags, and the no-score report design); drift as protocols vary (mitigated by evaluation on institutional documents during validation); security gaps if deployed beyond localhost without the production controls.

## Success measures for a pilot

Time-to-first-checklist, percentage of extraction fields confirmed correct by staff on sampling, reduction in clarification cycles, and a security review pass — all defined **before** the pilot, measured during, reported honestly after.
