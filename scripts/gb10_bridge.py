#!/usr/bin/env python3
"""Local OpenAI-compatible bridge backed by the Hermes CLI.

Machine-specific deployment glue (NOT part of the app core): listens on
127.0.0.1 only and translates /v1/chat/completions into `hermes -z` calls
through the host's working provider route. The app itself stays a plain
OpenAI-compatible client pointing at this bridge via LLM_BASE_URL.

Usage: python scripts/gb10_bridge.py [--port 8893] [--provider "..."]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import threading
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DEFAULT_PROVIDER = "GLM 5.3 Flash - GB10 Stack"
HERMES = os.environ.get("HERMES_BIN", os.path.expanduser("~/.hermes/hermes-agent/.hermes/bin/hermes"))

MODELS = ["GLM-5.3-Flash-EXL3"]

app = FastAPI(title="gb10 bridge")
state = {"provider": DEFAULT_PROVIDER, "timeout": 240}
_lock = threading.Semaphore(2)  # bound concurrent hermes invocations


def _prompt_from_messages(messages: list[dict]) -> str:  # type: ignore[valid-type]
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = str(msg.get("content", ""))
        if role == "system":
            parts.append(f"[SYSTEM INSTRUCTIONS]\n{content}")
        elif role == "user":
            parts.append(f"[USER]\n{content}")
        else:
            parts.append(f"[ASSISTANT]\n{content}")
    parts.append("[ASSISTANT]")
    return "\n\n".join(parts)


def _call_hermes(prompt: str) -> str:  # type: ignore[valid-type]
    proc = subprocess.run(
        [HERMES, "-z", prompt, "--provider", state["provider"]],
        capture_output=True, text=True, timeout=state["timeout"], cwd="/tmp",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"hermes exit {proc.returncode}: {proc.stderr[-300:]}")
    return proc.stdout.strip()


def _completion_response(content: str, model: str) -> dict:  # type: ignore[valid-type]
    return {
        "id": f"chatcmpl-bridge-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/healthz")
def healthz() -> dict:  # type: ignore[valid-type]
    return {"ok": True, "bridge": True, "provider": state["provider"]}


@app.get("/v1/models")
def models() -> dict:  # type: ignore[valid-type]
    return {"object": "list", "data": [{"id": m, "object": "model"} for m in MODELS]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    messages = payload.get("messages") or []
    if not messages:
        return JSONResponse({"error": "messages required"}, status_code=400)
    model = payload.get("model") or MODELS[0]
    prompt = _prompt_from_messages(messages)

    with _lock:
        try:
            content = _call_hermes(prompt)
        except subprocess.TimeoutExpired:
            return JSONResponse({"error": "bridge timeout"}, status_code=504)
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)

    return JSONResponse(_completion_response(content, model))


def main() -> None:  # type: ignore[valid-type]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8893)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    args = parser.parse_args()
    state["provider"] = args.provider

    import uvicorn

    print(f"bridge on http://{args.host}:{args.port}/v1 -> hermes provider '{args.provider}'")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
