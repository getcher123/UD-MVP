from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    PDF_CONVERSION_ERROR = "PDF_CONVERSION_ERROR"
    AGENTQL_ERROR = "AGENTQL_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ServiceError(Exception):
    code: ErrorCode
    http_status: int
    message: str

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.code} ({self.http_status}): {self.message}"


# Backward-compat legacy pipeline errors (unused in new API but kept)
class ProcessingError(Exception):
    """Raised when file processing pipeline fails."""


class ConversionError(ProcessingError):
    pass


class ExtractionError(ProcessingError):
    pass


class NormalizationError(ProcessingError):
    pass


__all__ = [
    "ErrorCode",
    "ServiceError",
    "ProcessingError",
    "ConversionError",
    "ExtractionError",
    "NormalizationError",
]
