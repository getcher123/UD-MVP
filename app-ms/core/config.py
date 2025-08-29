from __future__ import annotations

from pathlib import Path
from pydantic import BaseSettings


ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Optional config for future use
    agentql_api_key: str | None = None
    default_query_path: str = str(ROOT / "queries" / "default_query.txt")

    class Config:
        env_prefix = ""
        env_file = None  # Set to ".env" if you plan to use dotenv


settings = Settings()

