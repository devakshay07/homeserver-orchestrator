from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import List, Optional

class Settings(BaseSettings):
    # Telegram
    telegram_token: SecretStr
    owner_telegram_id: int

    # Gemini
    gemini_keys: List[SecretStr]
    gemini_model_spec: str = "gemini-2.5-flash"
    gemini_model_review: str = "gemini-2.0-flash"

    # GitHub
    github_app_id: Optional[str] = None
    github_app_private_key_path: Optional[str] = None
    github_pat: Optional[SecretStr] = None
    github_owner: str

    # Paths
    workspace_dir: str = "data/workspaces"
    db_path: str = "data/homeserver.sqlite"
    chroma_db_path: str = "data/chroma"


    # Scheduling & Other
    timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"
    agy_timeout_seconds: int = 1800
    max_retries: int = 3
    workspace_max_age_days: int = 7
    disk_min_free_gb: float = 2.0
    chroma_max_collection_size: int = 5000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__"
    )

    def get_gemini_keys(self) -> list[str]:
        return [key.get_secret_value() for key in self.gemini_keys]

settings = Settings()
