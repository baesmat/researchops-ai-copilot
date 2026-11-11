"""ASGI entrypoint.

Run: python -m app.main   (or: uvicorn app.main:app)
"""

from __future__ import annotations

import uvicorn

from app.api.routes import create_app
from app.config import load_config


def main() -> None:
    cfg = load_config()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()

