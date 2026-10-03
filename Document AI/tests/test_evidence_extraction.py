import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
import fitz

from forgerylens.ocr.evidence_extractor import extract_text
from forgerylens.contracts.evidence import EvidenceStatus

@pytest.fixture
def native_pdf_page(tmp_path):
    pdf_path = tmp_path / "test_native_ext.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.insert_text(fitz.Point(50, 50), "Exact Known Text", fontsize=24)
    doc.save(pdf_path)
    # We must keep doc open so the page object is valid
    yield doc[0]
    doc.close()

@pytest.fixture
def empty_pdf_page(tmp_path):
    pdf_path = tmp_path / "test_empty_ext.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    doc.save(pdf_path)
    yield doc[0]
    doc.close()

@pytest.fixture
def dummy_image():
    return Image.new("RGB", (1000, 1000), color="white")

def test_extract_text_native_pdf(native_pdf_page, tmp_path):
    evidence, words = extract_text(native_pdf_page, tmp_path, "dummy_hash")
    
    assert evidence.status == EvidenceStatus.OK
    assert evidence.method == "pdf_text_layer"
    
    # Check exact known text
    extracted_full = " ".join([w["text"] for w in words])
    assert "Exact Known Text" in extracted_full
    assert len(words) == 3
    
    # Check raw output file is unchanged and exists
    assert evidence.raw_ref is not None
    with open(evidence.raw_ref, "r") as f:
        raw_data = json.load(f)
    assert "blocks" in raw_data

@patch("pytesseract.image_to_data")
@patch("pytesseract.get_tesseract_version")
def test_extract_text_image(mock_get_version, mock_image_to_data, dummy_image, tmp_path):
    mock_version = MagicMock()
    mock_version.base_version = "5.3.0"
    mock_get_version.return_value = mock_version
    
    mock_data = {
        "text": ["", "Mocked", "Text"],
        "level": [4, 5, 5],
        "conf": ["-1", "90.0", "40.0"],
        "left": [0, 100, 200],
        "top": [0, 50, 50],
        "width": [0, 50, 60],
        "height": [0, 20, 20]
    }
    mock_image_to_data.return_value = mock_data
    
    evidence, words = extract_text(dummy_image, tmp_path, "dummy_hash")
    
    assert evidence.status == EvidenceStatus.OK
    assert evidence.method == "ocr:tesseract"
    assert evidence.provenance.parameters["engine"] == "tesseract"
    
    assert len(words) == 2
    assert words[0]["text"] == "Mocked"
    assert words[0]["confidence"] == 90.0
    assert not words[0]["is_low_confidence"]
    
    assert words[1]["text"] == "Text"
    assert words[1]["confidence"] == 40.0
    assert words[1]["is_low_confidence"]
    
    # Check raw output
    assert evidence.raw_ref is not None
    with open(evidence.raw_ref, "r") as f:
        raw_data = json.load(f)
    assert raw_data["text"] == ["", "Mocked", "Text"]

def test_extract_text_blank_page(empty_pdf_page, tmp_path):
    evidence, words = extract_text(empty_pdf_page, tmp_path, "dummy_hash")
    
    assert evidence.status == EvidenceStatus.OK
    assert len(words) == 0
    
    assert evidence.raw_ref is not None
    with open(evidence.raw_ref, "r") as f:
        raw_data = json.load(f)
    # Check no invented text
    text_blocks = [b for b in raw_data.get("blocks", []) if b.get("type") == 0]
    assert len(text_blocks) == 0

def test_unsupported_page_type(tmp_path):
    with pytest.raises(ValueError):
        extract_text("not_a_page", tmp_path)
