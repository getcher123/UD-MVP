import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load variables from the .env file located at the project root.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    bot_token: str = os.getenv("BOT_TOKEN", "")


settings = Settings()
