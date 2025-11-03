from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError

from core.errors import ErrorCode, ServiceError
from utils.fs import ensure_dir, safe_name

logger = logging.getLogger("service.pdf_to_images")


SUPPORTED_FORMATS = {"png", "jpeg"}


def pdf_to_images(
    pdf_path: str,
    out_dir: str,
    dpi: int = 150,
    image_format: str = "png",
    poppler_path: Optional[str] = None,
) -> List[str]:
    """Render each PDF page into an image file and return their paths."""
    source = Path(pdf_path)
    if not source.exists() or not source.is_file():
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, f"PDF not found: {pdf_path}")

    fmt = image_format.lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in SUPPORTED_FORMATS:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, f"Unsupported image format: {image_format}")

    ensure_dir(out_dir)

    try:
        images = convert_from_path(str(source), dpi=dpi, fmt=fmt, poppler_path=poppler_path)
    except PDFInfoNotInstalledError as exc:
        logger.error("Poppler missing for pdf2image", extra={"path": str(source)})
        raise ServiceError(
            ErrorCode.PDF_CONVERSION_ERROR,
            422,
            "Poppler is required for PDF rasterization. Install Poppler and set POPPLER_PATH or pipeline pdf_to_images.poppler_path."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to rasterize PDF", extra={"path": str(source)})
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, f"Failed to convert PDF to images: {exc}") from exc

    if not images:
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, "PDF rendered zero pages")

    base = safe_name(source.stem or "page")
    saved_paths: List[str] = []
    out_dir_path = Path(out_dir)

    for idx, image in enumerate(images, start=1):
        page_name = f"{base}_p{idx:04d}.{fmt}"
        target = out_dir_path / page_name
        try:
            save_format = "JPEG" if fmt == "jpeg" else fmt.upper()
            image.save(str(target), format=save_format)
        finally:
            image.close()
        saved_paths.append(str(target))

    return saved_paths


__all__ = ["pdf_to_images"]
