from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Response

from core.config import get_settings
from core.config_loader import get_rules
from core.errors import ErrorCode, ServiceError
from core.ids import new_job_id
from services.agentql_client import run_agentql
from services.listings import flatten_objects_to_listings
from services.excel_export import build_xlsx
from services.normalize import normalize_agentql_payload
from services.pdf_convert import to_pdf
from utils.fs import (
    build_result_path,
    enforce_size_limit,
    is_allowed_type,
    write_bytes,
    write_text,
)


router = APIRouter(tags=["process"])
settings = get_settings()


@router.post("/process_file")
async def process_file(
    file: UploadFile = File(...),
    query: Optional[str] = Form(None),
    request_id: Optional[str] = Form(None),
    output: Optional[str] = Form("excel"),
) -> dict:
    start_ts = time.perf_counter()
    req_id = (request_id or new_job_id())
    filename = file.filename or "upload"

    # Save upload to a temp path under results dir for traceability
    src_path = build_result_path(req_id, filename, base_dir=settings.RESULTS_DIR)
    data = await file.read()
    write_bytes(src_path, data)

    # Validate type/size
    try:
        enforce_size_limit(src_path, settings.MAX_FILE_MB)
    except ValueError as e:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, str(e))
    if not is_allowed_type(src_path, settings.ALLOW_TYPES):
        raise ServiceError(ErrorCode.UNSUPPORTED_TYPE, 400, f"Unsupported file type: {Path(src_path).suffix}")

    # Convert to PDF if needed
    try:
        pdf_path = to_pdf(str(src_path), settings.PDF_TMP_DIR)
    except ServiceError:
        # propagate explicit conversion errors
        raise
    except Exception as e:  # noqa: BLE001
        raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, f"Failed to convert to PDF: {e}")

    # Persist converted PDF next to results for traceability (if different from source)
    try:
        pdf_src = Path(pdf_path)
        if pdf_src.exists():
            pdf_dest = build_result_path(req_id, pdf_src.name, base_dir=settings.RESULTS_DIR)
            if str(pdf_dest) != str(pdf_src):
                write_bytes(pdf_dest, pdf_src.read_bytes())
    except Exception:
        # Non-fatal: continue even if we failed to copy PDF
        pass

    # Load default query if not provided
    query_text: str
    if query and query.strip():
        query_text = query
    else:
        qpath = Path(settings.DEFAULT_QUERY_PATH)
        if not qpath.exists():
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Default query not found: {qpath}")
        query_text = qpath.read_text(encoding="utf-8")

    # Call AgentQL
    try:
        aql_resp = run_agentql(pdf_path, query_text, mode="standard")
    except ServiceError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, f"AgentQL failed: {e}")

    # Persist raw AgentQL response for debugging/traceability
    raw_path = build_result_path(req_id, "agentql.json", base_dir=settings.RESULTS_DIR)
    import json as _json
    try:
        write_text(raw_path, _json.dumps(aql_resp, ensure_ascii=False, indent=2))
    except Exception:
        # Non-fatal
        pass

    # Load rules
    rules = get_rules(settings.RULES_PATH)

    # Normalize AgentQL payload to domain objects
    payload = aql_resp if isinstance(aql_resp, dict) else {}
    objects, pending_questions = normalize_agentql_payload(payload, rules)

    # Flatten to listing rows
    rows = flatten_objects_to_listings(objects, rules, request_id=req_id, source_file=filename)

    # Export Excel (listings)
    columns = rules["output"]["listing_columns"]
    export_path = build_result_path(req_id, "listings.xlsx", base_dir=settings.RESULTS_DIR)
    xlsx_bytes = build_xlsx(rows, columns=columns)
    write_bytes(export_path, xlsx_bytes)

    # Build response
    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    listings_total = len(rows)
    excel_url = None
    if settings.BASE_URL:
        base = settings.BASE_URL.rstrip("/")
        excel_url = f"{base}/results/{req_id}/listings.xlsx"

    # Respect output format: excel (default) | json | both
    out_mode = (output or "excel").lower()
    if out_mode == "excel":
        headers = {"Content-Disposition": 'attachment; filename="listings.xlsx"'}
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    body = {
        "request_id": req_id,
        "items_count": len(rows),
        "objects": None,
        "excel_url": excel_url,
        "pending_questions": pending_questions,
        "meta": {
            "source_file": os.path.basename(filename),
            "listings_total": listings_total,
            "timing_ms": elapsed_ms,
            "agentql_mode": "standard",
        },
    }
    return body

