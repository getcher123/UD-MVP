import sys
from pathlib import Path
from types import SimpleNamespace

APP_MS_ROOT = Path(__file__).resolve().parents[2]
if str(APP_MS_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MS_ROOT))

import pytest

from core.errors import ServiceError
from services import pdf_to_images as mod


class DummyImage:
    def __init__(self):
        self.saved = []
        self.closed = False

    def save(self, path, format):
        self.saved.append((path, format))

    def close(self):
        self.closed = True


def test_pdf_to_images_happy_path(tmp_path, monkeypatch):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    images_out = tmp_path / "pages"

    dummy_images = [DummyImage(), DummyImage()]

    def fake_convert(source, dpi, fmt, **kwargs):  # noqa: ANN001
        assert Path(source) == pdf_path
        assert dpi == 150
        assert fmt == "png"
        assert "poppler_path" in kwargs
        return dummy_images

    monkeypatch.setattr(mod, "convert_from_path", fake_convert)

    results = mod.pdf_to_images(str(pdf_path), str(images_out), dpi=150, image_format="png")

    assert len(results) == 2
    assert all(Path(p).suffix == ".png" for p in results)
    assert all(img.closed for img in dummy_images)
    assert dummy_images[0].saved[0][1] == "PNG"


def test_pdf_to_images_requires_existing_pdf(tmp_path):
    with pytest.raises(ServiceError):
        mod.pdf_to_images(str(tmp_path / "missing.pdf"), str(tmp_path), dpi=150)


def test_pdf_to_images_unsupported_format(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    with pytest.raises(ServiceError):
        mod.pdf_to_images(str(pdf_path), str(tmp_path), image_format="tiff")
