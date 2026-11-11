# Deployment

## Local (no Docker)

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m app.main                 # API :8410
.venv/bin/streamlit run frontend/streamlit_app.py   # UI :8501
```

Copy `.env.example` → `.env` and set `LLM_*` for your endpoint.

## Docker Compose

```bash
LLM_BASE_URL=http://host.docker.internal:8893/v1 LLM_MODEL=GLM-5.3-Flash-EXL3 docker compose up --build
```

- `api` on `127.0.0.1:8410`, `ui` on `127.0.0.1:8501` — localhost-only by default.
- Persistent state in the `copilot-data` volume; healthchecks on both containers; graceful shutdown via uvicorn signals.
- The model endpoint stays external and env-configured. `host.docker.internal` is mapped for host-local bridges such as `scripts/gb10_bridge.py`.

## The optional local bridge

If your endpoint is reachable only through host-specific auth, `scripts/gb10_bridge.py` exposes a plain OpenAI-compatible `127.0.0.1:8893/v1` backed by the host's own CLI auth path:

```bash
python scripts/gb10_bridge.py --port 8893   # then LLM_BASE_URL=http://127.0.0.1:8893/v1
```

The app has no dependency on it — any reachable endpoint works.

## Operational notes

- Graceful shutdown: uvicorn handles SIGTERM; the app closes DB connections on shutdown.
 Backups = copy the data dir (SQLite WAL; checkpoint or stop first).
- Upgrade: pull, `pip install -e .`, restart; schema is created idempotently (`CREATE TABLE IF NOT EXISTS`).
- Logs: stdout; no telemetry.
