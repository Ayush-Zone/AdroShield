"""Pytest test fixtures for ForgeryLens ingestion tests."""

from pathlib import Path
import pytest
from PIL import Image


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Generate a minimal valid single-page PDF programmatically."""
    pdf_path = tmp_path / "valid_sample.pdf"
    img = Image.new("RGB", (300, 400), color="white")
    img.save(pdf_path, format="PDF")
    return pdf_path


@pytest.fixture
def multipage_pdf(tmp_path: Path) -> Path:
    """Generate a minimal valid 3-page PDF programmatically."""
    pdf_path = tmp_path / "multipage_sample.pdf"
    img1 = Image.new("RGB", (200, 300), color="white")
    img2 = Image.new("RGB", (250, 350), color="red")
    img3 = Image.new("RGB", (300, 400), color="blue")
    img1.save(pdf_path, format="PDF", save_all=True, append_images=[img2, img3])
    return pdf_path


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    """Generate a valid PNG image."""
    png_path = tmp_path / "valid_image.png"
    img = Image.new("RGB", (320, 240), color="green")
    img.save(png_path, format="PNG", dpi=(300, 300))
    return png_path


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    """Generate a valid JPEG image."""
    jpg_path = tmp_path / "valid_photo.jpg"
    img = Image.new("RGB", (400, 300), color="blue")
    img.save(jpg_path, format="JPEG", dpi=(72, 72))
    return jpg_path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """Generate an empty 0-byte file with .pdf extension."""
    path = tmp_path / "zero_bytes.pdf"
    path.write_bytes(b"")
    return path


@pytest.fixture
def empty_png(tmp_path: Path) -> Path:
    """Generate an empty 0-byte file with .png extension."""
    path = tmp_path / "zero_bytes.png"
    path.write_bytes(b"")
    return path


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Generate a file with PDF magic bytes but completely corrupted body."""
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\n%rubbish_corrupted_data_without_any_objects_or_catalog")
    return path


@pytest.fixture
def corrupt_png(tmp_path: Path) -> Path:
    """Generate a file with PNG magic bytes but truncated/corrupted chunk."""
    path = tmp_path / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00")
    return path


@pytest.fixture
def spoofed_pdf(tmp_path: Path) -> Path:
    """Generate a plain text file masquerading with a .pdf extension."""
    path = tmp_path / "fake_document.pdf"
    path.write_text("This is plain text masquerading as a PDF invoice.", encoding="utf-8")
    return path


@pytest.fixture
def spoofed_png(tmp_path: Path) -> Path:
    """Generate a plain text file masquerading with a .png extension."""
    path = tmp_path / "fake_photo.png"
    path.write_text("This is plain text masquerading as a PNG photo.", encoding="utf-8")
    return path


@pytest.fixture
def unsupported_doc(tmp_path: Path) -> Path:
    """Generate an unsupported file type (.docx)."""
    path = tmp_path / "contract.docx"
    path.write_bytes(b"PK\x03\x04\x14\x00\x06\x00mock_docx_file_header")
    return path
