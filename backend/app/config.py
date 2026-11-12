"""Application settings. Every secret comes from the environment (see .env.example)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), env_prefix="PITCHVISION_", extra="ignore")

    # SQLite by default. For PostgreSQL / Supabase set e.g.
    # PITCHVISION_DATABASE_URL=postgresql+psycopg://user:password@host:5432/pitchvision
    database_url: str = f"sqlite:///{BACKEND_DIR / 'pitchvision.db'}"
    secret_key: str = ""                      # JWT signing key; generated and stored locally if empty
    token_hours: int = 24 * 14
    upload_dir: str = str(BACKEND_DIR / "uploads")
    max_upload_mb: int = 200
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    run_migrations: bool = True

    def resolved_secret(self) -> str:
        if self.secret_key:
            return self.secret_key
        path = BACKEND_DIR / ".secret_key"          # git-ignored; never commit
        if path.exists():
            return path.read_text().strip()
        key = secrets.token_urlsafe(48)
        path.write_text(key)
        os.chmod(path, 0o600)
        return key


settings = Settings()
