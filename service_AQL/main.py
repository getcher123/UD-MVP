import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv, find_dotenv
from agentql.tools.sync_api import query_document


ALLOWED_EXTS = {".pdf", ".html", ".htm", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".pptx"}
DEFAULT_INPUT_DIR = Path("service_AQL/input")
DEFAULT_QUERY_PATH = Path("app-ms/queries/default_query.txt")


def ensure_api_key() -> str:
    # Load from shared .env if present
    load_dotenv(find_dotenv(usecwd=True))
    api_key = os.getenv("AGENTQL_API_KEY")
    if not api_key:
        print("❌ AGENTQL_API_KEY is not set in environment or .env", file=sys.stderr)
        sys.exit(2)
    # Ensure the variable is visible to AgentQL internals
    os.environ["AGENTQL_API_KEY"] = api_key
    return api_key


def read_query(query_path: Path) -> str:
    if not query_path.is_file():
        print(f"❌ Query file not found: {query_path}", file=sys.stderr)
        sys.exit(2)
    return query_path.read_text(encoding="utf-8")


def list_input_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            yield p


def to_json_path(inp: Path, out_dir: Path | None) -> Path:
    base = inp.stem + ".json"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / base
    return inp.with_suffix(".json")


def install_playwright_chromium() -> None:
    # Best-effort installation of Chromium for Playwright
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"⚠️ Playwright install failed: {type(e).__name__}: {e}", file=sys.stderr)


def run(input_dir: Path, output_dir: Path | None, query_path: Path, mode: str) -> int:
    ensure_api_key()
    query = read_query(query_path)

    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️ Created input directory: {input_dir} (place files to process here)")

    files = sorted(list(list_input_files(input_dir)))
    if not files:
        print(f"⚠️ Нет входных файлов с поддерживаемыми расширениями в папке: {input_dir}")
        return 0

    print(f"🔎 Найдено файлов для обработки: {len(files)}\n")
    ok = fail = 0
    for fp in files:
        out_path = to_json_path(fp, output_dir)
        try:
            resp = query_document(str(fp), query=query, mode=mode)
            out_path.write_text(json.dumps(resp, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            ok += 1
            print(f"✅ {fp.name} → {out_path.name}")
        except Exception as e:
            fail += 1
            print(f"❌ {fp.name} → ошибка: {type(e).__name__}: {e}")

    print("\n—— Итог ——")
    print(f"Успешно: {ok}")
    print(f"Ошибки : {fail}")
    return 0 if fail == 0 else 1


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AgentQL document query runner")
    p.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT_DIR, help="Папка с входными файлами")
    p.add_argument("--output", "-o", type=Path, default=None, help="Папка для JSON результатов (необязательно)")
    p.add_argument("--query", "-q", type=Path, default=DEFAULT_QUERY_PATH, help="Путь к файлу с запросом AgentQL")
    p.add_argument("--mode", type=str, default="standard", help="Режим AgentQL (например, standard)")
    p.add_argument("--install-playwright", action="store_true", help="Установить Chromium для Playwright перед запуском")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.install_playwright:
        install_playwright_chromium()
    return run(args.input, args.output, args.query, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())

