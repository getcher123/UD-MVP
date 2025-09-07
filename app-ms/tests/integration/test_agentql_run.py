from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest


# Resolve project root so imports like 'from services.agentql_client import run_agentql' work
root = Path(__file__).resolve()
while root.name not in {"app-ms", "app_ms"} and root.parent != root:
    root = root.parent
sys.path.insert(0, str(root))

from services.agentql_client import run_agentql  # type: ignore  # noqa: E402
from utils.fs import build_result_path, write_text  # type: ignore  # noqa: E402


@pytest.mark.skipif(not os.getenv("AGENTQL_API_KEY"), reason="AGENTQL_API_KEY is not set")
def test_agentql_run_and_save_json():
    # Input PDF and query
    pdf_path = Path("../service_AQL/input/вакантыне площади БЦ ИНТЕГРАЛ.pdf").resolve()
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")

    query_path = root / "queries" / "default_query.txt"
    assert query_path.exists(), f"Query file missing: {query_path}"
    query_text = query_path.read_text(encoding="utf-8")

    # Run AgentQL
    resp = run_agentql(str(pdf_path), query_text, mode="standard")
    assert isinstance(resp, dict)

    # Save JSON response
    request_id = "agentql_integral_pdf"
    out_path = build_result_path(request_id, "agentql.json", base_dir=root.parent / "data" / "results")
    write_text(out_path, json.dumps(resp, ensure_ascii=False, indent=2))

    assert out_path.exists()
    # Quick sanity: reload JSON
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)

