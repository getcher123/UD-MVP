from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Settings:
    AGENTQL_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "o3"
    DEFAULT_QUERY_PATH: str = "app-ms/queries/default_query.txt"
    CHATGPT_INSTRUCTIONS_PATH: str = "app-ms/config/chatgpt_instructions.txt"
    CHATGPT_SCHEMA_PATH: str = "app-ms/config/chatgpt_schema.json"
    RULES_PATH: str = "app-ms/config/defaults.yml"
    MAX_FILE_MB: int = 20
    ALLOW_TYPES: List[str] = field(default_factory=lambda: [
        "pdf",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "xlsm",
        "txt",
        "jpg",
        "jpeg",
        "png",
        "mp3",
        "wav",
        "m4a",
        "ogg",
        "aac",
    ])
    AUDIO_TYPES: List[str] = field(default_factory=lambda: [
        "mp3",
        "wav",
        "m4a",
        "ogg",
        "aac",
    ])
    EXCEL_TYPES: List[str] = field(default_factory=lambda: [
        "xls",
        "xlsx",
        "xlsm",
    ])
    DOCX_TYPES: List[str] = field(default_factory=lambda: [
        "docx",
    ])
    APP_AUDIO_URL: Optional[str] = "http://localhost:8001/v1/transcribe"
    APP_AUDIO_TIMEOUT: float = 120.0
    APP_AUDIO_LANGUAGE: Optional[str] = None
    APP_AUDIO_MODEL: Optional[str] = None
    PDF_TMP_DIR: str = "/tmp/pdf"
    RESULTS_DIR: str = "data/results"
    BASE_URL: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    MICROSERVICE_VERSION: str = "0.1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ALLOW_TYPES", [t.lower() for t in self.ALLOW_TYPES])
        object.__setattr__(self, "AUDIO_TYPES", [t.lower() for t in self.AUDIO_TYPES])
        object.__setattr__(self, "EXCEL_TYPES", [t.lower() for t in self.EXCEL_TYPES])
        object.__setattr__(self, "DOCX_TYPES", [t.lower() for t in self.DOCX_TYPES])


def _get_env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [part.strip() for part in raw.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    allow_types = _get_env_list(
        "ALLOW_TYPES",
        [
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "xlsm",
            "txt",
            "jpg",
            "jpeg",
            "png",
            "mp3",
            "wav",
            "m4a",
            "ogg",
            "aac",
        ],
    )
    audio_types = _get_env_list("AUDIO_TYPES", ["mp3", "wav", "m4a", "ogg", "aac"])
    excel_types = _get_env_list("EXCEL_TYPES", ["xls", "xlsx", "xlsm"])
    docx_types = _get_env_list("DOCX_TYPES", ["docx"])

    max_file_mb_str = os.getenv("MAX_FILE_MB")
    try:
        max_file_mb = int(max_file_mb_str) if max_file_mb_str is not None else 20
    except ValueError:
        max_file_mb = 20

    app_audio_timeout_str = os.getenv("APP_AUDIO_TIMEOUT")
    try:
        app_audio_timeout = float(app_audio_timeout_str) if app_audio_timeout_str else 120.0
    except (TypeError, ValueError):
        app_audio_timeout = 120.0

    pkg_root = Path(__file__).resolve().parents[1]
    default_query_path_fallback = str(pkg_root / "queries" / "default_query.txt")
    instructions_path_fallback = str(pkg_root / "config" / "chatgpt_instructions.txt")
    schema_path_fallback = str(pkg_root / "config" / "chatgpt_schema.json")
    rules_path_fallback = str(pkg_root / "config" / "defaults.yml")

    return Settings(
        AGENTQL_API_KEY=os.getenv("AGENTQL_API_KEY"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "o3"),
        DEFAULT_QUERY_PATH=os.getenv("DEFAULT_QUERY_PATH", default_query_path_fallback),
        CHATGPT_INSTRUCTIONS_PATH=os.getenv("CHATGPT_INSTRUCTIONS_PATH", instructions_path_fallback),
        CHATGPT_SCHEMA_PATH=os.getenv("CHATGPT_SCHEMA_PATH", schema_path_fallback),
        RULES_PATH=os.getenv("RULES_PATH", rules_path_fallback),
        MAX_FILE_MB=max_file_mb,
        ALLOW_TYPES=allow_types,
        AUDIO_TYPES=audio_types,
        EXCEL_TYPES=excel_types,
        DOCX_TYPES=docx_types,
        APP_AUDIO_URL=os.getenv("APP_AUDIO_URL", "http://localhost:8001/v1/transcribe"),
        APP_AUDIO_TIMEOUT=app_audio_timeout,
        APP_AUDIO_LANGUAGE=os.getenv("APP_AUDIO_LANGUAGE"),
        APP_AUDIO_MODEL=os.getenv("APP_AUDIO_MODEL"),
        PDF_TMP_DIR=os.getenv("PDF_TMP_DIR", "/tmp/pdf"),
        RESULTS_DIR=os.getenv("RESULTS_DIR", "data/results"),
        BASE_URL=os.getenv("BASE_URL"),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        MICROSERVICE_VERSION=os.getenv("MICROSERVICE_VERSION", "0.1.0"),
    )


__all__ = ["Settings", "get_settings"]
