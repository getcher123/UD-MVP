"""Utility helpers for working with files."""

from pathlib import Path


def save_bytes(path: Path, data: bytes) -> Path:
    """Save binary data to the given path."""
    path.write_bytes(data)
    return path
