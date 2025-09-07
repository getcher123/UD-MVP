from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache
from typing import List, Optional


@dataclass(frozen=True)
class Settings:
    AGENTQL_API_KEY: Optional[str] = None
    DEFAULT_QUERY_PATH: str = "app-ms/queries/default_query.txt"
    RULES_PATH: str = "app-ms/config/defaults.yml"
    MAX_FILE_MB: int = 20
    ALLOW_TYPES: List[str] = field(default_factory=lambda: [
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "jpg",
        "jpeg",
        "png",
    ])
    PDF_TMP_DIR: str = "/tmp/pdf"
    RESULTS_DIR: str = "data/results"
    BASE_URL: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    MICROSERVICE_VERSION: str = "0.1.0"

    def __post_init__(self) -> None:
        # Normalize types/values without exposing secrets
        object.__setattr__(self, "ALLOW_TYPES", [t.lower() for t in self.ALLOW_TYPES])


def _get_env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [part.strip() for part in raw.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Read from environment with safe parsing; do not log secrets
    allow_types = _get_env_list("ALLOW_TYPES", [
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "jpg",
        "jpeg",
        "png",
    ])

    max_file_mb_str = os.getenv("MAX_FILE_MB")
    try:
        max_file_mb = int(max_file_mb_str) if max_file_mb_str is not None else 20
    except ValueError:
        max_file_mb = 20

    # Build a robust default path for the query file relative to this package
    pkg_root = Path(__file__).resolve().parents[1]
    default_query_path_fallback = str(pkg_root / "queries" / "default_query.txt")

    return Settings(
        AGENTQL_API_KEY=os.getenv("AGENTQL_API_KEY"),
        DEFAULT_QUERY_PATH=os.getenv("DEFAULT_QUERY_PATH", default_query_path_fallback),
        RULES_PATH=os.getenv("RULES_PATH", "app-ms/config/defaults.yml"),
        MAX_FILE_MB=max_file_mb,
        ALLOW_TYPES=allow_types,
        PDF_TMP_DIR=os.getenv("PDF_TMP_DIR", "/tmp/pdf"),
        RESULTS_DIR=os.getenv("RESULTS_DIR", "data/results"),
        BASE_URL=os.getenv("BASE_URL"),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        MICROSERVICE_VERSION=os.getenv("MICROSERVICE_VERSION", "0.1.0"),
    )


__all__ = ["Settings", "get_settings"]
