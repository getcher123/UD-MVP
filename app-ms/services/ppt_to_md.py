from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile
import xml.etree.ElementTree as ET

SLIDE_PATH_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}

TITLE_PLACEHOLDERS = {"title", "ctrTitle", "subTitle"}


def _iter_paragraph_text(element: ET.Element) -> Iterable[str]:
    for paragraph in element.findall(".//a:p", NS):
        parts: list[str] = []
        for run in paragraph.findall(".//a:t", NS):
            if run.text:
                parts.append(run.text)
        text = "".join(parts).strip()
        if text:
            yield text


def _shape_is_title(shape: ET.Element) -> bool:
    for placeholder in shape.findall(".//p:ph", NS):
        placeholder_type = placeholder.get("{http://schemas.openxmlformats.org/presentationml/2006/main}type")
        if placeholder_type in TITLE_PLACEHOLDERS:
            return True
    return False


def _iter_tables(root: ET.Element) -> Iterable[list[list[str]]]:
    for graphic_frame in root.findall(".//p:graphicFrame", NS):
        table = graphic_frame.find(".//a:tbl", NS)
        if table is None:
            continue
        rows: list[list[str]] = []
        for tr in table.findall("a:tr", NS):
            row: list[str] = []
            for tc in tr.findall("a:tc", NS):
                cell_texts = list(_iter_paragraph_text(tc))
                row.append(" ".join(cell_texts).strip())
            rows.append(row)
        if rows:
            yield rows


def _escape_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").strip()


def _table_to_markdown(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    max_cols = max(len(row) for row in rows)
    if max_cols == 0:
        return []

    normalised: list[list[str]] = []
    for row in rows:
        padded = row + [""] * (max_cols - len(row))
        normalised.append([_escape_cell(cell) for cell in padded])

    header = normalised[0]
    if all(cell == "" for cell in header):
        header = [f"Column {idx + 1}" for idx in range(max_cols)]

    separator = ["---"] * max_cols
    markdown_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in normalised[1:]:
        markdown_lines.append("| " + " | ".join(row) + " |")
    return markdown_lines


def ppt_to_md_text(
    path: str | Path,
    *,
    heading_prefix: str = "# ",
    bullet_prefix: str = "- ",
    include_tables: bool = True,
) -> str:
    ppt_path = Path(path)
    if not ppt_path.exists():
        raise FileNotFoundError(f"PPT/PPTX not found: {ppt_path}")

    lines: list[str] = []

    with ZipFile(ppt_path) as archive:
        slide_entries: list[tuple[int, str]] = []
        for name in archive.namelist():
            match = SLIDE_PATH_RE.match(name)
            if match:
                slide_entries.append((int(match.group(1)), name))
        slide_entries.sort()

        for number, slide_name in slide_entries:
            xml_bytes = archive.read(slide_name)
            root = ET.fromstring(xml_bytes)

            title_parts: list[str] = []
            body: list[str] = []

            for shape in root.findall(".//p:sp", NS):
                paragraphs = list(_iter_paragraph_text(shape))
                if not paragraphs:
                    continue
                if _shape_is_title(shape):
                    title_parts.extend(paragraphs)
                else:
                    body.extend(paragraphs)

            title = " / ".join(title_parts) if title_parts else f"Slide {number}"
            lines.append(f"{heading_prefix}{title}".rstrip())

            for paragraph in body:
                prefix = bullet_prefix or ""
                lines.append(f"{prefix}{paragraph}".rstrip())

            if include_tables:
                for table in _iter_tables(root):
                    lines.extend(_table_to_markdown(table))

            lines.append("")

    markdown = "\n".join(lines).strip()
    if markdown:
        markdown += "\n"
    else:
        markdown = "\n"
    return markdown


__all__ = ["ppt_to_md_text"]
