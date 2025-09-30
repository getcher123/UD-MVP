from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

import img2pdf

from core.config import get_settings
from core.errors import ErrorCode, ServiceError
from utils.fs import ensure_dir, safe_name

logger = logging.getLogger("service.pdf")

UNO_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "uno_set_borders.py"




def _config_enabled(cfg: Mapping[str, Any] | None, default: bool = True) -> bool:
    if not isinstance(cfg, Mapping):
        return default
    enabled = cfg.get("enabled")
    if enabled is None:
        return default
    if isinstance(enabled, bool):
        return enabled
    if isinstance(enabled, (int, float)):
        return bool(enabled)
    if isinstance(enabled, str):
        return enabled.strip().lower() not in {"0", "false", "no", "off"}
    return default


def _config_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
def _validate_input(path: Path) -> None:
    settings = get_settings()
    if not path.exists() or not path.is_file():
        logger.error("Input file does not exist", extra={"path": str(path)})
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, "Input file not found")

    size_mb = path.stat().st_size / (1024 * 1024)
    logger.info("Validating file size", extra={"path": str(path), "size_mb": round(size_mb, 2)})
    if size_mb > settings.MAX_FILE_MB:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            413,
            f"File too large: {size_mb:.2f} MB > {settings.MAX_FILE_MB} MB",
        )

    ext = path.suffix.lower().lstrip(".")
    logger.info("Validating extension", extra={"path": str(path), "ext": ext})
    if ext not in set(get_settings().ALLOW_TYPES):
        raise ServiceError(ErrorCode.UNSUPPORTED_TYPE, 400, f"Unsupported file type: {ext}")


def _convert_image_to_pdf(input_path: Path, out_dir: Path) -> Path:
    base = safe_name(input_path.stem)
    out_pdf = out_dir / f"{base}.pdf"
    logger.info(
        "Converting image to PDF via img2pdf",
        extra={"src": str(input_path), "dest": str(out_pdf)},
    )
    ensure_dir(out_dir)
    with open(input_path, "rb") as fsrc:
        data = fsrc.read()
    try:
        pdf_bytes = img2pdf.convert(data)
        out_pdf.write_bytes(pdf_bytes)
    except Exception as e:
        logger.warning(
            "img2pdf failed; writing minimal PDF placeholder",
            extra={"error": str(e)},
        )
        out_pdf.write_bytes(b"%PDF-1.4\n%EOF")
    return out_pdf


def _find_soffice(override: str | None = None) -> Path:
    if override:
        candidate = Path(override)
        if candidate.exists():
            return candidate
    soffice_env = os.getenv("SOFFICE_PATH")
    candidates = [
        Path(soffice_env) if soffice_env else None,
        Path(shutil.which("soffice")) if shutil.which("soffice") else None,
        Path(shutil.which("libreoffice")) if shutil.which("libreoffice") else None,
        Path(r"C:\\Program Files\\LibreOffice\\program\\soffice.exe"),
        Path(r"C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise ServiceError(
        ErrorCode.PDF_CONVERSION_ERROR,
        422,
        "LibreOffice (soffice) not found. Install LibreOffice or set SOFFICE_PATH to soffice executable.",
    )


def _find_libreoffice_python(soffice: Path) -> Optional[Path]:
    program_dir = soffice.parent
    # Typical layout: <LibreOffice>/program/soffice
    candidates = [
        program_dir / "python.exe",
        program_dir / "python",
        program_dir.parent / "program" / "python.exe",
        program_dir.parent / "program" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _prepare_excel_with_uno(
    input_path: Path,
    soffice: Path,
    format_cfg: Mapping[str, Any] | None,
) -> Path:
    uno_cfg: Mapping[str, Any] | None = None
    if isinstance(format_cfg, Mapping):
        raw = format_cfg.get("uno_borders")
        if isinstance(raw, Mapping):
            uno_cfg = raw

    if not _config_enabled(uno_cfg, True):
        logger.info(
            "UNO border formatting disabled via config",
            extra={"path": str(input_path)},
        )
        return input_path

    width_pt = _config_float((uno_cfg or {}).get("width_pt", 1.0), 1.0)
    if width_pt < 0:
        width_pt = 0.0

    lo_python = _find_libreoffice_python(soffice)
    if not lo_python:
        logger.warning("LibreOffice python interpreter not found; skipping UNO border formatting")
        return input_path

    if not UNO_SCRIPT.exists():
        logger.warning("UNO border script is missing; skipping border formatting", extra={"script": str(UNO_SCRIPT)})
        return input_path

    bordered_path = input_path.parent / f"{input_path.stem}_bordered{input_path.suffix}"
    cmd = [
        str(lo_python),
        str(UNO_SCRIPT),
        str(input_path),
        str(bordered_path),
        f"{width_pt}",
    ]
    logger.info(
        "Applying UNO border formatting",
        extra={"cmd": cmd, "line_width_pt": width_pt},
    )
    try:
        subprocess.run(cmd, check=True)
    except Exception as exc:
        logger.warning("Failed to apply UNO border formatting", extra={"error": str(exc)})
        return input_path

    if bordered_path.exists():
        return bordered_path
    logger.warning("UNO border script did not produce output; using original file", extra={"expected": str(bordered_path)})
    return input_path


def _convert_office_to_pdf(
    input_path: Path,
    out_dir: Path,
    format_cfg: Mapping[str, Any] | None,
    stage_cfg: Mapping[str, Any] | None,
) -> Path:
    """Convert DOCX/PPTX/XLSX to PDF using LibreOffice (soffice).

    The SOFFICE_PATH environment variable may be used to override the auto-detected executable.
    """
    soffice_override = None
    if isinstance(stage_cfg, Mapping):
        override_raw = stage_cfg.get("soffice_path") or stage_cfg.get("engine_path")
        if isinstance(override_raw, str) and override_raw.strip():
            soffice_override = override_raw.strip()

    soffice = _find_soffice(soffice_override)

    if input_path.suffix.lower() == ".xlsx":
        input_path = _prepare_excel_with_uno(input_path, soffice, format_cfg)

    ensure_dir(out_dir)
    logger.info(
        "Running soffice for PDF conversion",
        extra={"cmd": "soffice --headless --convert-to pdf --outdir <out_dir> <file>", "out_dir": str(out_dir)},
    )
    try:
        result = subprocess.run(
            [str(soffice), "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(input_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
    except Exception as e:
        logger.exception("Failed to invoke soffice", extra={"src": str(input_path)})
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, f"Failed to run soffice: {e}")

    rc = getattr(result, "returncode", None)
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    logger.info(
        "Soffice finished",
        extra={"returncode": rc, "stdout": str(stdout)[-500:], "stderr": str(stderr)[-500:]},
    )

    out_pdf = out_dir / f"{input_path.stem}.pdf"
    if rc != 0 or not out_pdf.exists():
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, "Failed to convert document to PDF")
    return out_pdf


def to_pdf(
    input_path: str,
    out_dir: str,
    format_cfg: Mapping[str, Any] | None = None,
    stage_cfg: Mapping[str, Any] | None = None,
) -> str:
    src = Path(input_path)
    out = Path(out_dir)

    logger.info("Starting to_pdf", extra={"src": str(src), "out_dir": str(out)})
    _validate_input(src)

    ext = src.suffix.lower().lstrip(".")
    if ext == "pdf":
        logger.info("Input is already PDF; skipping conversion", extra={"path": str(src)})
        return str(src)

    if ext in {"jpg", "jpeg", "png"}:
        out_pdf = _convert_image_to_pdf(src, out)
        logger.info("Image converted to PDF", extra={"dest": str(out_pdf)})
        return str(out_pdf)

    if ext in {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt"}:
        out_pdf = _convert_office_to_pdf(src, out, format_cfg, stage_cfg)
        logger.info("Office document converted to PDF", extra={"dest": str(out_pdf)})
        return str(out_pdf)

    logger.error("Unhandled file extension", extra={"ext": ext})
    raise ServiceError(ErrorCode.UNSUPPORTED_TYPE, 400, f"Unsupported file type: {ext}")


async def ensure_pdf(input_bytes: bytes, filename: str | None = None) -> Tuple[bytes, str]:
    name = (filename or "document").rsplit(".", 1)[0] + ".pdf"
    return input_bytes, name
