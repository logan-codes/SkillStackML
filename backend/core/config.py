"""
core/config.py
──────────────
Central configuration loaded from the .env file.
All settings are available via `from core.config import settings`.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Server ──────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    LOG_LEVEL: str = "info"

    # ── Groq AI ─────────────────────────────────────────
    GROQ_API_KEY: str = ""
    VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    COMPARE_MODEL: str = "llama-3.3-70b-versatile"

    # ── CORS ────────────────────────────────────────────
    CORS_ORIGINS: str = "*"

    # ── Uploads ─────────────────────────────────────────
    MAX_UPLOAD_MB: int = 10

    # ── Derived helpers ─────────────────────────────────
    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a Python list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# ── Singleton ───────────────────────────────────────────────
settings = Settings()
