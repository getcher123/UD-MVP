from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Sequence


def _build_command(path: Path, to_format: str, extra_args: Sequence[str] | None) -> list[str]:
    cmd = ["pandoc", str(path), "-t", to_format]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def docx_to_md_text(
    path: str | Path,
    to_format: str = "gfm",
    extra_args: Sequence[str] | None = None,
) -> str:
    docx_path = Path(path)
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    command = _build_command(docx_path, to_format, extra_args)

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise RuntimeError(
            f"pandoc failed with exit code {exc.returncode}: {stderr or stdout}"
        ) from exc

    return result.stdout


__all__ = ["docx_to_md_text"]
