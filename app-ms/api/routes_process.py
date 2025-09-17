from __future__ import annotations

import json
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
from services.audio_client import transcribe_audio
from services.chatgpt_structured import extract_structured_objects
from services.excel_export import build_xlsx
from services.listings import flatten_objects_to_listings
from services.normalize import normalize_agentql_payload
from services.pdf_convert import to_pdf
from utils.fs import (
    build_result_path,
    enforce_size_limit,
    file_ext,
    is_allowed_type,
    write_bytes,
    write_text,
)


router = APIRouter(tags=["process"])
settings = get_settings()


def _persist_json(data: dict, req_id: str, name: str) -> None:
    try:
        target = build_result_path(req_id, name, base_dir=settings.RESULTS_DIR)
        write_text(target, json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:  # pragma: no cover - diagnostics helper
        pass


@router.post("/process_file")
async def process_file(
    file: UploadFile = File(...),
    query: Optional[str] = Form(None),
    request_id: Optional[str] = Form(None),
    output: Optional[str] = Form("excel"),
) -> dict:
    start_ts = time.perf_counter()
    req_id = request_id or new_job_id()
    filename = file.filename or "upload"

    src_path = build_result_path(req_id, filename, base_dir=settings.RESULTS_DIR)
    data = await file.read()
    write_bytes(src_path, data)

    try:
        enforce_size_limit(src_path, settings.MAX_FILE_MB)
    except ValueError as e:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, str(e))
    if not is_allowed_type(src_path, settings.ALLOW_TYPES):
        raise ServiceError(ErrorCode.UNSUPPORTED_TYPE, 400, f"Unsupported file type: {Path(src_path).suffix}")

    ext = file_ext(src_path)
    is_audio = ext in settings.AUDIO_TYPES

    payload: dict[str, object]
    pending_questions: list[dict[str, object]] = []
    pipeline_marker = "audio_chatgpt" if is_audio else "document_agentql"

    if is_audio:
        transcription = transcribe_audio(data, filename, settings)
        _persist_json(transcription, req_id, "app_audio_response.json")

        srt = transcription.get("srt") if isinstance(transcription, dict) else None
        if not isinstance(srt, str) or not srt.strip():
            raise ServiceError(ErrorCode.TRANSCRIPTION_ERROR, 424, "app-audio returned empty SRT payload")

        srt_name = f"{Path(filename).stem or 'audio'}.srt"
        try:
            write_text(build_result_path(req_id, srt_name, base_dir=settings.RESULTS_DIR), srt)
        except Exception:  # pragma: no cover - diagnostics helper
            pass

        payload = extract_structured_objects(srt)
        _persist_json(payload, req_id, "chatgpt_structured.json")
    else:
        try:
            pdf_path = to_pdf(str(src_path), settings.PDF_TMP_DIR)
        except ServiceError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, f"Failed to convert to PDF: {e}")

        try:
            pdf_src = Path(pdf_path)
            if pdf_src.exists():
                pdf_dest = build_result_path(req_id, pdf_src.name, base_dir=settings.RESULTS_DIR)
                if str(pdf_dest) != str(pdf_src):
                    write_bytes(pdf_dest, pdf_src.read_bytes())
        except Exception:  # pragma: no cover - diagnostics helper
            pass

        if query and query.strip():
            query_text = query
        else:
            qpath = Path(settings.DEFAULT_QUERY_PATH)
            if not qpath.exists():
                raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Default query not found: {qpath}")
            query_text = qpath.read_text(encoding="utf-8")

        try:
            aql_resp = run_agentql(pdf_path, query_text, mode="standard")
        except ServiceError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, f"AgentQL failed: {e}")

        if isinstance(aql_resp, dict):
            _persist_json(aql_resp, req_id, "agentql.json")
            payload = aql_resp
        else:
            _persist_json({"data": aql_resp}, req_id, "agentql.json")
            payload = {}

    rules = get_rules(settings.RULES_PATH)
    objects, pending_questions = normalize_agentql_payload(payload, rules)

    rows = flatten_objects_to_listings(objects, rules, request_id=req_id, source_file=filename)

    columns = rules["output"]["listing_columns"]
    export_path = build_result_path(req_id, "listings.xlsx", base_dir=settings.RESULTS_DIR)
    xlsx_bytes = build_xlsx(rows, columns=columns)
    write_bytes(export_path, xlsx_bytes)

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    listings_total = len(rows)
    excel_url = None
    if settings.BASE_URL:
        base = settings.BASE_URL.rstrip("/")
        excel_url = f"{base}/results/{req_id}/listings.xlsx"

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
            "pipeline": pipeline_marker,
            "agentql_mode": "standard" if not is_audio else None,
        },
    }

    return body
