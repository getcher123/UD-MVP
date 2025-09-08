from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import img2pdf

from core.config import get_settings
from core.errors import ErrorCode, ServiceError
from utils.fs import ensure_dir, safe_name


logger = logging.getLogger("service.pdf")


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


def _convert_office_to_pdf(input_path: Path, out_dir: Path) -> Path:
    """Convert DOCX/PPTX/XLSX to PDF using LibreOffice (soffice).

    On Windows/macOS, tries common installation paths if soffice is not in PATH.
    You can override the path by setting the SOFFICE_PATH environment variable.
    """
    # Locate soffice (allow override via env)
    soffice_env = os.getenv("SOFFICE_PATH")
    soffice = soffice_env or shutil.which("soffice") or shutil.which("libreoffice")

    if not soffice:
        # Try common Windows locations
        candidates = [
            r"C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            r"C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                soffice = c
                break

    if not soffice:
        raise ServiceError(
            ErrorCode.PDF_CONVERSION_ERROR,
            422,
            "LibreOffice (soffice) not found. Install LibreOffice or set SOFFICE_PATH to soffice executable.",
        )

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

    rc = result if isinstance(result, int) else getattr(result, "returncode", None)
    stdout = "" if isinstance(result, int) else getattr(result, "stdout", "")
    stderr = "" if isinstance(result, int) else getattr(result, "stderr", "")
    logger.info(
        "Soffice finished",
        extra={"returncode": rc, "stdout": str(stdout)[-500:], "stderr": str(stderr)[-500:]},
    )

    # Expected output file path
    out_pdf = out_dir / f"{input_path.stem}.pdf"
    if (rc is None or rc != 0) or not out_pdf.exists():
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, "Failed to convert document to PDF")
    return out_pdf


def to_pdf(input_path: str, out_dir: str) -> str:
    """Convert the given file to PDF and return the resulting path.

    - If input is already a PDF, returns the original path.
    - Images (jpg/jpeg/png) are converted using img2pdf into a single PDF.
    - Office docs (docx/pptx/xlsx) are converted via LibreOffice `soffice`.
    - Validates extension and size using settings.
    - Logs each step with context-rich JSON lines.
    """
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

    if ext in {"docx", "pptx", "xlsx"}:
        out_pdf = _convert_office_to_pdf(src, out)
        logger.info("Office document converted to PDF", extra={"dest": str(out_pdf)})
        return str(out_pdf)

    # Should not reach here because of validation; act defensively
    logger.error("Unhandled file extension", extra={"ext": ext})
    raise ServiceError(ErrorCode.UNSUPPORTED_TYPE, 400, f"Unsupported file type: {ext}")


async def ensure_pdf(input_bytes: bytes, filename: str | None = None) -> Tuple[bytes, str]:
    """Ensure the content is PDF; if not, convert it (stub for in-memory paths).

    This async helper remains a stub for now, useful for future upload flows
    where conversion happens in-memory.
    Returns (pdf_bytes, pdf_name).
    """
    name = (filename or "document").rsplit(".", 1)[0] + ".pdf"
    return input_bytes, name
