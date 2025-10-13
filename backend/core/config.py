from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Allow selecting which .env to read (host vs docker)
ENV_FILE = os.environ.get(
    "ENV_FILE",
    str(Path(__file__).resolve().parent.parent / ".env"),
)


class Settings(BaseSettings):
    # ---- App ----
    app_name: str = "PetMatch"
    env: str = "development"
    debug: bool = True
    api_v1_str: str = "/api/v1"

    # ---- Security ----
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---- DB ----
    database_url: str = "sqlite:///./dev.db"

    # ---- Other ----
    log_level: str = "info"
    cors_allow_origins: list[str] = ["*"]
    MEDIA_DIR: str = "media"
    MEDIA_BASE_URL: str = "/media"
    PHOTO_MAX_BYTES: int = 2_000_000
    PHOTO_ALLOWED: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Robust parser for CORS_ALLOW_ORIGINS:
    # - "", "*"            -> ["*"]
    # - '["a","b"]' (JSON) -> ["a","b"]
    # - "a,b,c"            -> ["a","b","c"]
    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if not isinstance(v, str):
            return ["*"]
        s = v.strip()
        if not s or s == "*":
            return ["*"]
        if s.startswith("["):
            try:
                arr = json.loads(s)
                return [str(x).strip() for x in arr if str(x).strip()]
            except Exception:
                pass  # fallback to comma-split
        return [part.strip() for part in s.split(",") if part.strip()]


settings = Settings()
