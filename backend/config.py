"""
Application configuration via environment variables.

All settings have safe defaults for local development.
In production (Railway), set these via the dashboard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # ── Server ───────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    WORKERS: int = 1  # Railway free tier: keep at 1
    LOG_LEVEL: str = "info"

    # ── CORS ─────────────────────────────────────────────────
    # Comma-separated origins, or "*" to allow all.
    CORS_ORIGINS: str = "*"

    # ── Limits ───────────────────────────────────────────────
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MAX_AUDIO_SECONDS: float = 15.0           # reject chunks > 15s
    MAX_AUDIO_SAMPLE_RATE: int = 48000
    REQUEST_TIMEOUT_S: float = 30.0           # per-request budget

    # ── DSP ──────────────────────────────────────────────────
    TARGET_SAMPLE_RATE: int = 16000
    FRAME_SIZE: int = 2048

    # ── AI / Vision ────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""  # empty = vision OMR disabled

    # ── Rate Limiting ──────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60       # max requests per window
    RATE_LIMIT_WINDOW_S: int = 60       # sliding window in seconds

    # ── Auth ─────────────────────────────────────────────────
    JWT_SECRET: str = "dev-secret-change-in-production"

    # ── App ──────────────────────────────────────────────────
    APP_VERSION: str = "0.4.0"
    ENVIRONMENT: str = "development"  # development | staging | production


def load_config() -> Config:
    """Load config from environment, falling back to defaults."""
    fields = Config.__dataclass_fields__
    kwargs = {}
    for name, f in fields.items():
        env_val = os.environ.get(name)
        if env_val is not None:
            # Coerce to the field's type
            if f.type == "int":
                kwargs[name] = int(env_val)
            elif f.type == "float":
                kwargs[name] = float(env_val)
            else:
                kwargs[name] = env_val
    return Config(**kwargs)


# Singleton — import this everywhere
settings = load_config()
