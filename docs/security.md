# Security & Privacy

## Implemented controls

- **Local-only binding.** API and UI default to `127.0.0.1` (compose maps `127.0.0.1:`). Nothing is exposed without explicit action.
- **No telemetry, no analytics, no phoning home.** The only outbound calls are to the model endpoint you configure.
- **Upload validation** (`app/security/file_validation.py`): extension allow-list (pdf/docx), magic-byte signature check, configurable size cap (default 15 MB), NFKC normalization, directory-component stripping (path traversal), length cap. Stored under generated ids, never user-controlled paths.
- **Untrusted-document handling. Uploaded content is parsed, never executed. Rendering libraries are the only code touching it; the app does not fetch remote references, does not follow links, and disables auto-retrieval. A `Content-Type` mismatch is rejected with a clear error.
- **Prompt-injection defenses** (`app/security/input_sanitization.py` + service design):
  - system instructions and document content travel in separate prompt segments; document text is framed as *data*;
  - control characters stripped, lengths capped;
  - citations validated against the known chunk-id set before display;
  - no shell, filesystem, or tool execution exists in the request path — there is nothing for an injected instruction to trigger.
  - Adversarial fixture: a synthetic protocol contains an embedded `ignore previous instructions` block; `tests/test_api.py::test_prompt_injection_is_data_not_instructions` asserts structural separation.
- **Error hygiene.** API errors are short messages; exception details are logged server-side only. Credentials never appear in responses (`llm_client.llm_config_snapshot` explicitly strips keys).
- **Data lifecycle.** Deletion cascades across `analyses`, `checklist_items`, `qa_log` and removes stored files (verified by test). `DOC_RETENTION_DAYS` configures retention intent; expiry sweeping is a documented TODO, not implemented.
- **Supply chain.** `pip-audit` + `bandit` in CI; dependencies deliberately minimal.

## Limits of the injection defenses (honest disclosure)

A validated citation id proves the id exists, and the lexical check (`_supports`, ≥30% token overlap) is a heuristic — a determined document can still steer the *content* of a summary within the excerpts. The model can also paraphrase incorrectly inside a valid citation. The `verified`/`grounded` flags reduce but do not eliminate this; human review remains mandatory (the UI says so on every item).

## What production would add (not implemented — no false claims)

SSO/OIDC, RBAC per study, audit logging, encryption at rest, network segmentation, data classification review, institutional security review, approved model hosting (incl. BAA where PHI is touched), retention/deletion policy enforcement, backup/DR. **The application does not claim HIPAA compliance**; it is a synthetic-data demonstration.
