# UD-MVP Microservice (app-ms)

Purpose: accept a file → convert to PDF → run through AgentQL → normalize → return Excel/JSON.

This microservice exposes a simple HTTP API that receives an uploaded file, performs a
conversion and extraction pipeline, and returns a structured result. The intended flow is:

- Input: User uploads a document or image (PDF/DOCX/PPTX/XLSX/JPG/PNG, etc.).
- Convert: If not already PDF, convert the file to PDF.
- Extract: Run the PDF through AgentQL using a predefined query to extract tabular data.
- Normalize: Clean and normalize the extracted data for consistent downstream usage.
- Output: Return an Excel workbook (and/or JSON) containing the normalized results.

This repository currently ships with a runnable stub implementation:

- `POST /process_file` accepts `multipart/form-data` with fields `file=@...` and `chat_id`.
- It returns a small example Excel file to demonstrate the I/O contract.
- Replace the placeholder service functions under `services/` with real implementations.

## Endpoints

- `GET /health` — health check.
- `POST /process_file` — accepts a file and returns an Excel file.

## Local Run

```bash
cd app-ms
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## Environment

Common variables you might add as you implement real logic:

- `AGENTQL_API_KEY` — API key for AgentQL
- `DEFAULT_QUERY_PATH` — path to the default AgentQL query file (defaults to `queries/default_query.txt`)

