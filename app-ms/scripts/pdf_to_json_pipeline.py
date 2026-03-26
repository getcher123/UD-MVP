from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import get_settings
from core.config_loader import get_rules
from core.errors import ErrorCode, ServiceError
from core.ids import new_job_id
from services.chatgpt_structured import extract_structured_objects
from services.chatgpt_vision import analyze_page_image
from services.pdf_to_images import pdf_to_images
from utils.fs import ensure_dir, file_ext, write_text

logger = logging.getLogger("scripts.pdf_to_json_pipeline")


def _get_pipeline_cfg(rules: Mapping[str, Any]) -> Mapping[str, Any]:
    pipeline = rules.get("pipeline") if isinstance(rules, Mapping) else None
    return pipeline if isinstance(pipeline, Mapping) else {}


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


def _write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def run_pipeline(
    input_pdf: Path,
    *,
    results_dir: Path,
    request_id: str,
    dpi: int | None = None,
    image_format: str | None = None,
    poppler_path: str | None = None,
    prompt_path: str | None = None,
    model: str | None = None,
    save_pages: bool = True,
    run_structured: bool = True,
) -> Path:
    settings = get_settings()
    rules = get_rules(settings.RULES_PATH)
    pipeline_cfg = _get_pipeline_cfg(rules)

    if file_ext(input_pdf) != "pdf":
        raise ServiceError(ErrorCode.VALIDATION_ERROR, 400, f"Input must be a PDF: {input_pdf}")

    images_stage_cfg = _get_stage_cfg(pipeline_cfg, "pdf", "pdf_to_images")
    if not _cfg_enabled(images_stage_cfg, True):
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "PDF to images disabled via configuration")

    dpi_value = dpi if dpi is not None else images_stage_cfg.get("dpi")
    try:
        dpi_final = int(dpi_value) if dpi_value is not None else 150
    except (TypeError, ValueError):
        dpi_final = 150

    format_value = image_format or images_stage_cfg.get("format") or images_stage_cfg.get("image_format")
    if isinstance(format_value, str) and format_value.strip():
        image_format_final = format_value.strip().lower()
    else:
        image_format_final = "png"

    poppler_override = poppler_path or images_stage_cfg.get("poppler_path")
    if isinstance(poppler_override, str) and poppler_override.strip():
        poppler_final = poppler_override.strip()
    else:
        poppler_final = settings.POPPLER_PATH

    pages_dir = results_dir / request_id / "pdf_pages"
    ensure_dir(pages_dir)

    start_ts = time.perf_counter()
    logger.info("pipeline.start", extra={"pdf": str(input_pdf), "request_id": request_id})

    page_images = pdf_to_images(
        str(input_pdf),
        str(pages_dir),
        dpi=dpi_final,
        image_format=image_format_final,
        poppler_path=poppler_final,
    )

    vision_stage_cfg = _get_stage_cfg(pipeline_cfg, "pdf", "vision_per_page")
    if not _cfg_enabled(vision_stage_cfg, True):
        raise ServiceError(ErrorCode.INTERNAL_ERROR, 503, "PDF vision stage disabled via configuration")

    prompt_override = prompt_path or vision_stage_cfg.get("prompt_path") or vision_stage_cfg.get("prompt")
    if isinstance(prompt_override, str) and prompt_override.strip():
        prompt_final = prompt_override.strip()
    else:
        prompt_final = None

    model_override = model or vision_stage_cfg.get("model")
    if isinstance(model_override, str) and model_override.strip():
        model_final = model_override.strip()
    else:
        model_final = None

    page_payloads: list[dict[str, Any]] = []
    out_dir = results_dir / request_id
    ensure_dir(out_dir)

    for idx, image_path in enumerate(page_images, start=1):
        page_data = analyze_page_image(image_path, prompt_path=prompt_final, model=model_final)
        if isinstance(page_data, dict) and "page_index" not in page_data:
            page_data["page_index"] = idx
        page_payloads.append(page_data)

        if save_pages:
            _write_json(out_dir / f"pdf_page_{idx:04d}.json", page_data)
            _write_json(out_dir / "pdf_pages_combined.json", page_payloads)

    chatgpt_stage_cfg = _get_stage_cfg(pipeline_cfg, "pdf", "chatgpt_structured")
    if run_structured and _cfg_enabled(chatgpt_stage_cfg, True):
        payload = extract_structured_objects(page_payloads)
    else:
        payload = {"objects": []}

    output_path = out_dir / "chatgpt_structured.json"
    _write_json(output_path, payload)

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    logger.info("pipeline.done", extra={"elapsed_ms": elapsed_ms, "output": str(output_path)})
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PDF -> JSON pipeline (vision + structured)")
    parser.add_argument("-i", "--input", required=True, help="Path to PDF file")
    parser.add_argument("-o", "--output", help="Override output JSON path")
    parser.add_argument("--results-dir", help="Base results dir (default: settings.RESULTS_DIR)")
    parser.add_argument("--request-id", help="Request id (default: random)")
    parser.add_argument("--dpi", type=int, help="Override PDF raster DPI")
    parser.add_argument("--image-format", help="Override image format (png/jpeg)")
    parser.add_argument("--poppler-path", help="Override POPPLER_PATH")
    parser.add_argument("--prompt-path", help="Override vision prompt path")
    parser.add_argument("--model", help="Override vision model")
    parser.add_argument("--no-pages", action="store_true", help="Do not save per-page JSON files")
    parser.add_argument("--no-structured", action="store_true", help="Skip structured extraction stage")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s:%(name)s:%(message)s")

    input_pdf = Path(args.input).expanduser()
    if not input_pdf.exists():
        print(f"Input PDF not found: {input_pdf}", file=sys.stderr)
        return 2

    settings = get_settings()
    results_dir = Path(args.results_dir) if args.results_dir else Path(settings.RESULTS_DIR)
    request_id = args.request_id or new_job_id()

    try:
        output_path = run_pipeline(
            input_pdf,
            results_dir=results_dir,
            request_id=request_id,
            dpi=args.dpi,
            image_format=args.image_format,
            poppler_path=args.poppler_path,
            prompt_path=args.prompt_path,
            model=args.model,
            save_pages=not args.no_pages,
            run_structured=not args.no_structured,
        )
    except ServiceError as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Pipeline crashed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        target = Path(args.output)
        ensure_dir(target.parent)
        target.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Saved: {target}")
    else:
        print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
