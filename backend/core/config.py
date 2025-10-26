# C:\Dev\Yunus\backend\core\config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List

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
    access_token_expire_minutes: int = 60  # .env: ACCESS_TOKEN_EXPIRE_MINUTES

    # Eski kodla uyumluluk (security.py 'jwt_expires_minutes' bekliyor)
    @property
    def jwt_expires_minutes(self) -> int:
        return self.access_token_expire_minutes

    # ---- Database ----
    database_url: str = f"sqlite:///{(BASE_DIR / 'dev.db').as_posix()}"

    # ---- Other ----
    log_level: str = "info"
    cors_allow_origins: List[str] = ["*"]

    # Pydantic Settings config
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),  # backend/.env
        env_prefix="",                    # prefix yok
        case_sensitive=False,             # .env'de büyük/küçük fark etmez
        extra="ignore",                   # tanımsız anahtarları yoksay
    )

settings = Settings()
