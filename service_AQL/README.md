Service AQL

Purpose: Run AgentQL queries against local documents using Playwright, reading the query from `app-ms/queries/default_query.txt` and the API key from the shared `.env`.

Setup
- Create a dedicated virtual environment for this service.
- Install dependencies from `service_AQL/requirements.txt`.
- Install the Chromium browser for Playwright.

Commands
- Python: 3.10+

Example
1) Create and activate venv (Windows PowerShell):
   python -m venv .venv_aql
   .\.venv_aql\Scripts\Activate.ps1

2) Install deps:
   pip install -r service_AQL/requirements.txt

3) Install Chromium for Playwright:
   python -m playwright install chromium

4) Put input files into `service_AQL/input` (pdf, html, docx, txt, png, jpg, jpeg, pptx).

5) Run the service:
   python -m service_AQL --input service_AQL/input --query app-ms/queries/default_query.txt

Options
- `--input` (`-i`): Directory with files to process. Default: `service_AQL/input`.
- `--output` (`-o`): Optional output directory for JSON. If omitted, writes next to inputs.
- `--query` (`-q`): Path to query file. Default: `app-ms/queries/default_query.txt`.
- `--mode`: AgentQL mode (e.g. `standard`). Default: `standard`.
- `--install-playwright`: Install Chromium via Playwright before running.

Notes
- The API key is loaded from the shared `.env` in the project root: `AGENTQL_API_KEY=...`.
- Outputs are JSON files named after each input, with `.json` extension.

