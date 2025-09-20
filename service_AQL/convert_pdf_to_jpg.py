from __future__ import annotations

from pathlib import Path

import fitz

INPUT_DIR = Path(__file__).resolve().parent / "input"
OUTPUT_DIR = INPUT_DIR / "jpg"
DEFAULT_DPI = 300


def iter_pdf_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def convert_pdf_to_jpgs(pdf_path: Path, base_output_dir: Path, dpi: int = DEFAULT_DPI) -> list[Path]:
    doc_output_dir = base_output_dir / pdf_path.stem
    doc_output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    saved: list[Path] = []
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
            output_name = f"{pdf_path.stem}_page_{page_index + 1:02d}.jpg"
            output_path = doc_output_dir / output_name
            pix.save(output_path)
            saved.append(output_path)
    finally:
        doc.close()
    return saved


def main() -> int:
    pdf_files = iter_pdf_files(INPUT_DIR)
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving pages to: {OUTPUT_DIR}")

    for pdf_path in pdf_files:
        print(f"Processing {pdf_path.name}...")
        saved_paths = convert_pdf_to_jpgs(pdf_path, OUTPUT_DIR)
        print(f"  Saved {len(saved_paths)} pages")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
