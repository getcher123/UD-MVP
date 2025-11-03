from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


def _build_command(path: Path, to_format: str, extra_args: Sequence[str] | None) -> list[str]:
    cmd = ["pandoc", str(path), "-t", to_format]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _find_soffice() -> Path:
    candidates: list[Path | None] = []
    env_override = os.getenv("SOFFICE_PATH")
    if env_override:
        candidates.append(Path(env_override))
    soffice_bin = shutil.which("soffice")
    if soffice_bin:
        candidates.append(Path(soffice_bin))
    libreoffice_bin = shutil.which("libreoffice")
    if libreoffice_bin:
        candidates.append(Path(libreoffice_bin))
    candidates.extend(
        [
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        ]
    )
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise RuntimeError(
        "LibreOffice (soffice) not found. Install LibreOffice or set SOFFICE_PATH to the soffice executable."
    )


def _convert_doc_to_docx(src: Path, out_dir: Path) -> Path:
    soffice = _find_soffice()
    cmd = [str(soffice), "--headless", "--convert-to", "docx", "--outdir", str(out_dir), str(src)]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    converted = out_dir / f"{src.stem}.docx"
    if result.returncode != 0 or not converted.exists():
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        message = stderr or stdout or "Unknown error"
        raise RuntimeError(f"LibreOffice failed to convert DOC to DOCX: {message}")
    return converted


def _pandoc_to_md(path: Path, to_format: str, extra_args: Sequence[str] | None) -> str:
    command = _build_command(path, to_format, extra_args)
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - pass back diagnostic
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise RuntimeError(
            f"pandoc failed with exit code {exc.returncode}: {stderr or stdout}"
        ) from exc
    return result.stdout


def docx_to_md_text(
    path: str | Path,
    to_format: str = "gfm",
    extra_args: Sequence[str] | None = None,
) -> str:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Word document not found: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix == ".doc":
        with tempfile.TemporaryDirectory() as tmp_dir:
            converted = _convert_doc_to_docx(source_path, Path(tmp_dir))
            return _pandoc_to_md(converted, to_format, extra_args)

    return _pandoc_to_md(source_path, to_format, extra_args)


__all__ = ["docx_to_md_text"]
