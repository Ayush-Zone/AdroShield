"""Tests for document ingestion and preliminary validation."""

from pathlib import Path
from forgerylens import ingest_document, DocumentFormat, IngestionStatus


def test_valid_pdf(sample_pdf: Path):
    """Test 1: Ingesting a valid single-page PDF."""
    doc = ingest_document(sample_pdf, evidence_id="TEST-PDF-001")

    assert doc.document_id == "TEST-PDF-001"
    assert doc.status == IngestionStatus.VALID
    assert doc.is_valid is True
    assert doc.format == DocumentFormat.PDF
    assert doc.mime_type == "application/pdf"
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == 1
    assert doc.pages[0].width > 0
    assert doc.pages[0].height > 0
    assert doc.pages[0].is_readable is True
    assert len(doc.errors) == 0


def test_multipage_pdf(multipage_pdf: Path):
    """Test 2: Ingesting a valid multi-page PDF."""
    doc = ingest_document(multipage_pdf, evidence_id="TEST-PDF-MULTI")

    assert doc.status == IngestionStatus.VALID
    assert doc.is_valid is True
    assert doc.page_count == 3
    assert len(doc.pages) == 3
    for i, page in enumerate(doc.pages, start=1):
        assert page.page_number == i
        assert page.width > 0
        assert page.height > 0
        assert page.is_readable is True


def test_valid_png(sample_png: Path):
    """Test 3: Ingesting a valid PNG image."""
    doc = ingest_document(sample_png, evidence_id="TEST-PNG-001")

    assert doc.status == IngestionStatus.VALID
    assert doc.is_valid is True
    assert doc.format == DocumentFormat.PNG
    assert doc.mime_type == "image/png"
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].width == 320.0
    assert doc.pages[0].height == 240.0
    assert doc.pages[0].dpi == 300
    assert len(doc.errors) == 0


def test_valid_jpeg(sample_jpeg: Path):
    """Test 4: Ingesting a valid JPEG image."""
    doc = ingest_document(sample_jpeg, evidence_id="TEST-JPG-001")

    assert doc.status == IngestionStatus.VALID
    assert doc.is_valid is True
    assert doc.format == DocumentFormat.JPEG
    assert doc.mime_type == "image/jpeg"
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].width == 400.0
    assert doc.pages[0].height == 300.0
    assert len(doc.errors) == 0


def test_missing_file(tmp_path: Path):
    """Test 5: Ingesting a nonexistent file path."""
    missing_path = tmp_path / "does_not_exist.pdf"
    doc = ingest_document(missing_path)

    assert doc.status == IngestionStatus.UNREADABLE
    assert doc.is_valid is False
    assert any("file not found" in err.lower() for err in doc.errors)


def test_empty_pdf_file(empty_pdf: Path):
    """Test 6: Ingesting an empty 0-byte PDF file."""
    doc = ingest_document(empty_pdf)

    assert doc.status == IngestionStatus.EMPTY
    assert doc.is_valid is False
    assert any("empty file" in err.lower() for err in doc.errors)


def test_empty_png_file(empty_png: Path):
    """Test 7: Ingesting an empty 0-byte PNG file."""
    doc = ingest_document(empty_png)

    assert doc.status == IngestionStatus.EMPTY
    assert doc.is_valid is False
    assert any("empty file" in err.lower() for err in doc.errors)


def test_corrupt_pdf(corrupt_pdf: Path):
    """Test 8: Ingesting a corrupted PDF file."""
    doc = ingest_document(corrupt_pdf)

    assert doc.status == IngestionStatus.CORRUPT
    assert doc.is_valid is False
    assert doc.page_count == 0
    assert any("corrupt pdf" in err.lower() for err in doc.errors)


def test_corrupt_image(corrupt_png: Path):
    """Test 9: Ingesting a corrupted image file."""
    doc = ingest_document(corrupt_png)

    assert doc.status == IngestionStatus.CORRUPT
    assert doc.is_valid is False
    assert doc.page_count == 0
    assert any("corrupt image" in err.lower() for err in doc.errors)


def test_spoofed_pdf_extension(spoofed_pdf: Path):
    """Test 10: Ingesting a text file masquerading as a .pdf."""
    doc = ingest_document(spoofed_pdf)

    assert doc.status == IngestionStatus.CORRUPT
    assert doc.is_valid is False
    assert any("does not match expected pdf" in err.lower() for err in doc.errors)


def test_spoofed_png_extension(spoofed_png: Path):
    """Test 11: Ingesting a text file masquerading as a .png."""
    doc = ingest_document(spoofed_png)

    assert doc.status == IngestionStatus.CORRUPT
    assert doc.is_valid is False
    assert any("does not match expected png" in err.lower() for err in doc.errors)


def test_unsupported_document_type(unsupported_doc: Path):
    """Test 12: Ingesting an unsupported file format (.docx)."""
    doc = ingest_document(unsupported_doc)

    assert doc.status == IngestionStatus.UNSUPPORTED
    assert doc.is_valid is False
    assert any("unsupported document type" in err.lower() for err in doc.errors)


def test_file_size_limit_exceeded(sample_pdf: Path):
    """Test 13: Enforcing maximum file size threshold."""
    # Set limit below the sample PDF size
    doc = ingest_document(sample_pdf, max_file_size_bytes=50)

    assert doc.status == IngestionStatus.UNREADABLE
    assert doc.is_valid is False
    assert any("exceeds maximum allowed size" in err.lower() for err in doc.errors)


def test_directory_path_rejected(tmp_path: Path):
    """Test 14: Ingesting a directory path should fail gracefully."""
    doc = ingest_document(tmp_path)

    assert doc.status == IngestionStatus.UNREADABLE
    assert doc.is_valid is False
    assert any("not a regular file" in err.lower() for err in doc.errors)


def test_generated_evidence_id(sample_png: Path):
    """Test 15: If evidence_id is not provided, a UUID is automatically assigned."""
    doc = ingest_document(sample_png)

    assert doc.document_id is not None
    assert len(doc.document_id) >= 32
