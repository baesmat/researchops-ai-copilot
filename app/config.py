"""Configuration from environment variables. Nothing is hardcoded.

All model access is via OpenAI-compatible env vars; the app never assumes a
specific provider, host, or credential.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_VERSION = "0.1.0"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass
class LLMConfig:
    base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "http://localhost:8080/v1"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL", "not-configured"))
    api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", ""))
    timeout_s: int = field(default_factory=lambda: _env_int("LLM_TIMEOUT_SECONDS", 120))
    max_output_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_OUTPUT_TOKENS", 4096))
    temperature: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.1")))

    def is_configured(self) -> bool:
        return bool(self.base_url) and self.model != "not-configured"


@dataclass
class AppConfig:
    db_path: Path = field(default_factory=lambda: Path(_env("APP_DB_PATH", "data/copilot.db")))
    data_dir: Path = field(default_factory=lambda: Path(_env("APP_DATA_DIR", "data")))
    # upload limits
    max_upload_mb: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_MB", 15))
    # retention for uploaded documents, 0 = keep until deleted
    retention_days: int = field(default_factory=lambda: _env_int("DOC_RETENTION_DAYS", 0))
    host: str = field(default_factory=lambda: _env("APP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("APP_PORT", 8410))
    llm: LLMConfig = field(default_factory=LLMConfig)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_config() -> AppConfig:
    return AppConfig()
