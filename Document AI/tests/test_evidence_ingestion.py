import pytest
from pathlib import Path
import fitz
from PIL import Image
from forgerylens.contracts.evidence import EvidenceStatus
from forgerylens.ingestion.evidence_ingestor import ingest_document_evidence
from forgerylens.utils.hash import calculate_file_sha256

@pytest.fixture
def minimal_pdf(tmp_path):
    path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path

@pytest.fixture
def multipage_pdf(tmp_path):
    path = tmp_path / "multi.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path

@pytest.fixture
def minimal_png(tmp_path):
    path = tmp_path / "test.png"
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(path)
    return path

def test_pdf_ingest(minimal_pdf, tmp_path):
    storage_dir = tmp_path / "storage"
    record, pages = ingest_document_evidence(minimal_pdf, storage_dir)
    assert record.status == EvidenceStatus.OK
    assert record.observation["page_count"] == 1
    assert len(pages) == 1
    assert record.provenance.source_file_sha256 == calculate_file_sha256(minimal_pdf)
    assert record.raw_ref is not None
    assert Path(record.raw_ref).exists()
    assert calculate_file_sha256(minimal_pdf) == calculate_file_sha256(record.raw_ref)

def test_multipage_pdf_ingest(multipage_pdf, tmp_path):
    storage_dir = tmp_path / "storage"
    record, pages = ingest_document_evidence(multipage_pdf, storage_dir)
    assert record.status == EvidenceStatus.OK
    assert record.observation["page_count"] == 3
    assert len(pages) == 3

def test_image_ingest(minimal_png, tmp_path):
    storage_dir = tmp_path / "storage"
    record, pages = ingest_document_evidence(minimal_png, storage_dir)
    assert record.status == EvidenceStatus.OK
    assert record.observation["format"] == "image/png"
    assert len(pages) == 1
    
def test_unsupported_type_rejected(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello")
    storage_dir = tmp_path / "storage"
    record, pages = ingest_document_evidence(path, storage_dir)
    assert record.status == EvidenceStatus.NOT_ANALYZABLE
    assert "error" in record.observation
    assert "Unsupported file type" in record.observation["error"]

def test_corrupt_file_handled(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a pdf file")
    storage_dir = tmp_path / "storage"
    record, pages = ingest_document_evidence(path, storage_dir)
    assert record.status == EvidenceStatus.NOT_ANALYZABLE
    assert "error" in record.observation
    assert "Corrupt or unreadable file" in record.observation["error"]
