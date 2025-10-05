from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from fastapi import APIRouter, UploadFile, File, Form, Response

from core.config import get_settings
from core.config_loader import get_rules
from core.errors import ErrorCode, ServiceError
from core.ids import new_job_id
from services.agentql_client import run_agentql
from services.audio_client import transcribe_audio
from services.chatgpt_structured import extract_structured_objects
from services.excel_export import build_xlsx
from services.excel_to_csv import excel_to_csv_text
from services.docx_to_md import docx_to_md_text
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


def _get_pipeline_cfg(rules: Mapping[str, Any]) -> Mapping[str, Any]:
    pipeline = rules.get("pipeline") if isinstance(rules, Mapping) else None
    return pipeline if isinstance(pipeline, Mapping) else {}


def _get_format_cfg(pipeline_cfg: Mapping[str, Any], fmt: str) -> Mapping[str, Any]:
    raw = pipeline_cfg.get(fmt) if isinstance(pipeline_cfg, Mapping) else None
    return raw if isinstance(raw, Mapping) else {}


def _get_stage_cfg(pipeline_cfg: Mapping[str, Any], fmt: str, stage: str) -> Mapping[str, Any]:
    cfg: dict[str, Any] = {}
    common = pipeline_cfg.get("common") if isinstance(pipeline_cfg, Mapping) else None
    if isinstance(common, Mapping):
        stage_common = common.get(stage)
        if isinstance(stage_common, Mapping):
            cfg.update(stage_common)
    fmt_cfg = pipeline_cfg.get(fmt) if isinstance(pipeline_cfg, Mapping) else None
    if isinstance(fmt_cfg, Mapping):
        stage_specific = fmt_cfg.get(stage)
        if isinstance(stage_specific, Mapping):
            cfg.update(stage_specific)
    return cfg


def _cfg_enabled(cfg: Mapping[str, Any] | None, default: bool = True) -> bool:
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


def _detect_format(ext: str, is_audio: bool) -> str:
    if is_audio:
        return "audio"
    if ext == "docx":
        return "docx"
    if ext == "doc":
        return "doc"
    if ext in {"ppt", "pptx"}:
        return "ppt"
    if ext in {"xls", "xlsx", "xlsm"}:
        return "excel"
    if ext == "pdf":
        return "pdf"
    if ext in {"jpg", "jpeg", "png"}:
        return "image"
    if ext == "txt":
        return "txt"
    return "doc"


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
    is_docx = ext in settings.DOCX_TYPES
    is_excel = ext in settings.EXCEL_TYPES

    rules = get_rules(settings.RULES_PATH)
    pipeline_cfg = _get_pipeline_cfg(rules)
    fmt_key = _detect_format(ext, is_audio)
    format_cfg = _get_format_cfg(pipeline_cfg, fmt_key)

    pipeline_steps: list[str] = []
    if fmt_key:
        pipeline_steps.append(fmt_key)

    payload: dict[str, object]
    pending_questions: list[dict[str, object]] = []
    agentql_mode_meta: Optional[str] = None

    if is_audio:
        transcription_cfg = _get_stage_cfg(pipeline_cfg, "audio", "transcription")
        if not _cfg_enabled(transcription_cfg, True):
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "Audio transcription disabled via configuration")

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

        pipeline_steps.append("transcription")

        chatgpt_cfg = _get_stage_cfg(pipeline_cfg, "audio", "chatgpt_structured")
        if _cfg_enabled(chatgpt_cfg, True):
            payload = extract_structured_objects(srt)
            pipeline_steps.append("chatgpt_structured")
            _persist_json(payload, req_id, "chatgpt_structured.json")
        else:
            payload = {"objects": []}
            pipeline_steps.append("chatgpt_skip")
    elif is_excel:
        convert_cfg = _get_stage_cfg(pipeline_cfg, "excel", "excel_to_csv")
        if not _cfg_enabled(convert_cfg, True):
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "Excel to CSV disabled via configuration")

        try:
            csv_text = excel_to_csv_text(src_path)
        except Exception as exc:  # noqa: BLE001
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Failed to convert Excel to CSV: {exc}")

        csv_name = f"{Path(filename).stem or 'workbook'}.csv"
        try:
            write_text(build_result_path(req_id, csv_name, base_dir=settings.RESULTS_DIR), csv_text)
        except Exception:  # pragma: no cover - diagnostics helper
            pass

        pipeline_steps.append("excel_to_csv")

        chatgpt_cfg = _get_stage_cfg(pipeline_cfg, "excel", "chatgpt_structured")
        if not _cfg_enabled(chatgpt_cfg, True):
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "Excel ChatGPT disabled via configuration")

        payload = extract_structured_objects(csv_text)
        pipeline_steps.append("chatgpt_structured")
        _persist_json(payload, req_id, "chatgpt_structured.json")
    elif is_docx:
        convert_cfg = _get_stage_cfg(pipeline_cfg, "docx", "docx_to_md")
        if not _cfg_enabled(convert_cfg, True):
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "DOCX to Markdown disabled via configuration")

        to_format = "gfm"
        if isinstance(convert_cfg, dict):
            format_value = convert_cfg.get("to_format") or convert_cfg.get("to") or convert_cfg.get("format")
            if isinstance(format_value, str) and format_value.strip():
                to_format = format_value.strip()

            args_value = convert_cfg.get("args")
            extra_args = None
            if isinstance(args_value, (list, tuple)):
                extra_args = [str(arg) for arg in args_value]
            elif isinstance(args_value, str) and args_value.strip():
                extra_args = [arg for arg in args_value.split() if arg]
        else:
            extra_args = None

        try:
            md_text = docx_to_md_text(src_path, to_format=to_format, extra_args=extra_args)
        except Exception as exc:  # noqa: BLE001
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 500, f"Failed to convert DOCX to Markdown: {exc}")

        md_name = f"{Path(filename).stem or 'document'}.md"
        try:
            write_text(build_result_path(req_id, md_name, base_dir=settings.RESULTS_DIR), md_text)
        except Exception:  # pragma: no cover - diagnostics helper
            pass

        pipeline_steps.append("docx_to_md")

        chatgpt_cfg = _get_stage_cfg(pipeline_cfg, "docx", "chatgpt_structured")
        if not _cfg_enabled(chatgpt_cfg, True):
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "DOCX ChatGPT disabled via configuration")

        payload = extract_structured_objects(md_text)
        pipeline_steps.append("chatgpt_structured")
        _persist_json(payload, req_id, "chatgpt_structured.json")
    else:
        pdf_stage_cfg = _get_stage_cfg(pipeline_cfg, fmt_key, "pdf_conversion")
        pdf_enabled_default = fmt_key != "pdf"
        if _cfg_enabled(pdf_stage_cfg, pdf_enabled_default):
            try:
                pdf_path = to_pdf(str(src_path), settings.PDF_TMP_DIR, format_cfg, pdf_stage_cfg)
            except ServiceError:
                raise
            except Exception as e:  # noqa: BLE001
                raise ServiceError(ErrorCode.PDF_CONVERSION_ERROR, 422, f"Failed to convert to PDF: {e}")
            pipeline_steps.append("pdf_conversion")
        else:
            if ext != "pdf":
                raise ServiceError(
                    ErrorCode.PDF_CONVERSION_ERROR,
                    503,
                    f"PDF conversion disabled for format '{fmt_key}'",
                )
            pdf_path = str(src_path)

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

        agentql_stage_cfg = _get_stage_cfg(pipeline_cfg, fmt_key, "agentql")
        if _cfg_enabled(agentql_stage_cfg, True):
            agentql_kwargs: dict[str, Any] = {}
            mode_value = agentql_stage_cfg.get("mode")
            if isinstance(mode_value, str) and mode_value.strip():
                agentql_kwargs["mode"] = mode_value.strip()
            else:
                agentql_kwargs["mode"] = "standard"
            timeout_value = agentql_stage_cfg.get("timeout_sec")
            if timeout_value is not None:
                try:
                    agentql_kwargs["timeout_sec"] = float(timeout_value)
                except (TypeError, ValueError):
                    pass

            agentql_mode_meta = agentql_kwargs.get("mode")

            try:
                aql_resp = run_agentql(pdf_path, query_text, **agentql_kwargs)
            except ServiceError:
                raise
            except Exception as e:  # noqa: BLE001
                raise ServiceError(ErrorCode.AGENTQL_ERROR, 424, f"AgentQL failed: {e}")

            pipeline_steps.append("agentql")

            if isinstance(aql_resp, dict):
                _persist_json(aql_resp, req_id, "agentql.json")
                payload = aql_resp
            else:
                _persist_json({"data": aql_resp}, req_id, "agentql.json")
                payload = {}
        else:
            payload = {"objects": []}
            pipeline_steps.append("agentql_skip")

    objects, pending_questions = normalize_agentql_payload(payload, rules)

    rows = flatten_objects_to_listings(objects, rules, request_id=req_id, source_file=filename)

    excel_stage_cfg = _get_stage_cfg(pipeline_cfg, "postprocess", "excel_export")
    excel_enabled = _cfg_enabled(excel_stage_cfg, True)

    columns: list[object] = []
    xlsx_bytes: bytes | None = None
    export_path = None
    if excel_enabled:
        raw_columns = rules["output"]["listing_columns"]
        for col in raw_columns:
            if isinstance(col, str) and "|" in col:
                key, header = [part.strip() for part in col.split("|", 1)]
                if not key:
                    continue
                columns.append((key, header or key))
            else:
                columns.append(col)
        export_path = build_result_path(req_id, "listings.xlsx", base_dir=settings.RESULTS_DIR)
        xlsx_bytes = build_xlsx(rows, columns=columns)
        write_bytes(export_path, xlsx_bytes)
        pipeline_steps.append("excel_export")

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    listings_total = len(rows)

    pipeline_marker = "_".join(step for step in pipeline_steps if step)

    excel_url = None
    if excel_enabled and settings.BASE_URL and export_path is not None:
        base = settings.BASE_URL.rstrip("/")
        excel_url = f"{base}/results/{req_id}/listings.xlsx"

    out_mode = (output or "excel").lower()
    if out_mode == "excel":
        if not excel_enabled or xlsx_bytes is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "Excel export disabled via configuration")
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
            "agentql_mode": agentql_mode_meta,
        },
    }

    return body
