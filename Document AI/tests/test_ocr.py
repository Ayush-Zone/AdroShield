"""Tests for the ForgeryLens OCR / Text Extraction phase."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

import fitz  # PyMuPDF

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import IngestedDocument, PageInfo
from forgerylens.contracts.ocr import OCRExtractionMethod, OCRResult, OCRWord
from forgerylens.ocr.orchestrator import extract_document_text
from forgerylens.ocr.engines.tesseract import extract_words_from_image
from forgerylens.ocr.engines.pdf import extract_words_from_pdf_page


@pytest.fixture
def dummy_image_path(tmp_path):
    img_path = tmp_path / "test_img.png"
    img = Image.new("RGB", (1000, 1000), color="white")
    img.save(img_path)
    return img_path


@pytest.fixture
def dummy_ingested_image(dummy_image_path):
    return IngestedDocument(
        document_id="img-123",
        source_path=str(dummy_image_path),
        filename="test_img.png",
        file_size_bytes=1024,
        mime_type="image/png",
        format=DocumentFormat.PNG,
        page_count=1,
        pages=[PageInfo(page_number=1, width=1000, height=1000)],
        status=IngestionStatus.VALID
    )


@pytest.fixture
def native_pdf_path(tmp_path):
    pdf_path = tmp_path / "test_native.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.insert_text(fitz.Point(50, 50), "Hello World OCR", fontsize=24)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def dummy_ingested_pdf(native_pdf_path):
    return IngestedDocument(
        document_id="pdf-123",
        source_path=str(native_pdf_path),
        filename="test_native.pdf",
        file_size_bytes=4096,
        mime_type="application/pdf",
        format=DocumentFormat.PDF,
        page_count=1,
        pages=[PageInfo(page_number=1, width=500, height=500)],
        status=IngestionStatus.VALID
    )


# ---------------------------------------------------------
# Unit Tests for Engines
# ---------------------------------------------------------

def test_extract_words_from_pdf_page(native_pdf_path):
    """Test native PDF extraction logic using PyMuPDF."""
    doc = fitz.open(native_pdf_path)
    page = doc[0]
    full_text, words, warnings = extract_words_from_pdf_page(page, 500, 500)
    
    assert not warnings
    assert "Hello" in full_text
    assert "World" in full_text
    
    assert len(words) == 3
    assert words[0].text == "Hello"
    assert words[0].confidence is None
    # Check normalized bounds (0 to 1)
    assert 0.0 < words[0].x < 1.0
    assert 0.0 < words[0].y < 1.0
    
    doc.close()


@patch("pytesseract.image_to_data")
def test_extract_words_from_image_mocked(mock_image_to_data):
    """Test Tesseract wrapper with mocked pytesseract output."""
    mock_data = {
        "text": ["", "Hello", "Mock"],
        "level": [4, 5, 5],
        "conf": ["-1", "95.5", "80.0"],
        "left": [0, 100, 200],
        "top": [0, 50, 50],
        "width": [0, 50, 60],
        "height": [0, 20, 20]
    }
    mock_image_to_data.return_value = mock_data
    
    img = Image.new("RGB", (1000, 1000), color="white")
    full_text, words, warnings = extract_words_from_image(img)
    
    assert not warnings
    assert full_text == "Hello Mock"
    assert len(words) == 2
    
    assert words[0].text == "Hello"
    assert words[0].confidence == 95.5
    assert words[0].x == 0.1  # 100 / 1000
    assert words[0].y == 0.05 # 50 / 1000
    
    assert words[1].text == "Mock"
    assert words[1].confidence == 80.0
    assert words[1].x == 0.2


# ---------------------------------------------------------
# Integration / Orchestrator Tests
# ---------------------------------------------------------

def test_orchestrator_native_pdf(dummy_ingested_pdf):
    """Test full orchestrator path for a native text PDF."""
    result = extract_document_text(dummy_ingested_pdf)
    
    assert result.is_valid
    assert result.document_id == "pdf-123"
    assert len(result.pages) == 1
    
    page = result.pages[0]
    assert page.page_number == 1
    assert page.extraction_method == OCRExtractionMethod.NATIVE_PDF
    assert "Hello World" in page.full_text
    assert len(page.words) == 3


@patch("forgerylens.ocr.orchestrator.extract_words_from_image")
def test_orchestrator_image(mock_extract, dummy_ingested_image):
    """Test orchestrator for images."""
    mock_extract.return_value = ("Test Image", [
        OCRWord(text="Test", confidence=90.0, x=0, y=0, width=0.1, height=0.1)
    ], [])
    
    result = extract_document_text(dummy_ingested_image)
    
    assert result.is_valid
    assert len(result.pages) == 1
    
    page = result.pages[0]
    assert page.extraction_method == OCRExtractionMethod.TESSERACT_OCR
    assert page.full_text == "Test Image"


@patch("forgerylens.ocr.orchestrator.extract_words_from_image")
def test_orchestrator_scanned_pdf(mock_extract, tmp_path):
    """Test orchestrator fallback from PDF native to rendering/OCR."""
    # Create a PDF with no text, just an image/drawing to simulate scan
    pdf_path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.draw_rect(fitz.Rect(50, 50, 450, 450), color=(1, 0, 0), fill=(1, 0, 0))
    doc.save(pdf_path)
    doc.close()
    
    ingested = IngestedDocument(
        document_id="scan-123",
        source_path=str(pdf_path),
        filename="scanned.pdf",
        file_size_bytes=4096,
        mime_type="application/pdf",
        format=DocumentFormat.PDF,
        page_count=1,
        pages=[PageInfo(page_number=1, width=500, height=500)],
        status=IngestionStatus.VALID
    )
    
    # Mock OCR returning some words
    mock_extract.return_value = ("Scanned Content", [
        OCRWord(text="Scanned", confidence=90.0, x=0, y=0, width=0.1, height=0.1)
    ], [])
    
    result = extract_document_text(ingested)
    
    assert result.is_valid
    assert len(result.pages) == 1
    assert result.pages[0].extraction_method == OCRExtractionMethod.TESSERACT_OCR
    assert result.pages[0].full_text == "Scanned Content"


def test_orchestrator_invalid_ingested_document(dummy_ingested_image):
    """Ensure OCR skips and propagates errors for already invalid documents."""
    dummy_ingested_image.status = IngestionStatus.CORRUPT
    dummy_ingested_image.errors = ["Previous error"]
    
    result = extract_document_text(dummy_ingested_image)
    assert not result.is_valid
    assert result.status == IngestionStatus.CORRUPT
    assert "Previous error" in result.errors
    assert len(result.pages) == 0
