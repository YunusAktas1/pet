from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---- App ----
    app_name: str = "PetMatch"
    env: str = "development"
    debug: bool = True
    api_v1_str: str = "/api/v1"

    # ---- Security ----
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30  # .env: ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = 14  # .env: REFRESH_TOKEN_EXPIRE_DAYS

    # Backward compatibility (security.py expects jwt_expires_minutes)
    @property
    def jwt_expires_minutes(self) -> int:
        return self.access_token_expire_minutes

    # ---- Database ----
    database_url: str = f"sqlite:///{(BASE_DIR / 'dev.db').as_posix()}"

    # ---- Other ----
    log_level: str = "info"
    cors_allow_origins: list[str] = ["*"]

    # ---- Media / Photo ----
    MEDIA_DIR: str = "media"
    MEDIA_BASE_URL: str = "/media"
    PHOTO_ALLOWED: list[str] = ["image/jpeg", "image/png", "image/webp"]
    PHOTO_MAX_BYTES: int = 5 * 1024 * 1024  # 5MB

    # Pydantic Settings config
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),  # backend/.env
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
