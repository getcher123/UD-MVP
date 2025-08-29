from __future__ import annotations


class ProcessingError(Exception):
    """Raised when file processing pipeline fails."""


class ConversionError(ProcessingError):
    pass


class ExtractionError(ProcessingError):
    pass


class NormalizationError(ProcessingError):
    pass

