from __future__ import annotations

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Form, Response

from services.excel_export import build_xlsx


router = APIRouter(tags=["process"])


@router.post("/process_file")
async def process_file(
    file: Annotated[UploadFile, File(...)],
    chat_id: Annotated[str, Form(...)],
) -> Response:
    # Read file content (stub path: skip actual conversion and AgentQL)
    content = await file.read()

    # Build demo Excel with a couple of cells showing metadata
    xlsx_bytes = build_xlsx([
        {"chat_id": chat_id, "filename": file.filename or "unknown", "size": len(content)},
    ])

    headers = {"Content-Disposition": 'attachment; filename="result.xlsx"'}
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )

