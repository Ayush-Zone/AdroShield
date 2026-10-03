import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PIL import Image

from forgerylens.contracts.enums import IngestionStatus, DocumentFormat
from forgerylens.contracts.structured import DocumentType
from forgerylens.contracts.evidence import EvidenceStatus, EvidenceBundle, EvidenceRecord, Provenance
from forgerylens.contracts.document import IngestedDocument, PageInfo
from forgerylens.pipeline import run_pipeline
import uuid

@pytest.fixture
def dummy_invoice_pdf(tmp_path):
    import fitz
    pdf_path = tmp_path / "invoice.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.insert_text(fitz.Point(50, 50), "Invoice Total: $100.00", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)

def test_pipeline_missing_file():
    with pytest.raises(FileNotFoundError):
        run_pipeline("nonexistent_file_path.pdf")

@patch("forgerylens.pipeline.ingest_document")
@patch("forgerylens.pipeline.extract_document_text")
@patch("forgerylens.pipeline.classify_document")
@patch("forgerylens.pipeline.extract_invoice_pack")
@patch("forgerylens.pipeline.run_all_consistency_checks")
@patch("forgerylens.pipeline.analyze_pdf")
@patch("forgerylens.pipeline.analyze_pixels")
def test_pipeline_happy_path(
    mock_pixels, mock_meta_pdf, mock_cons, mock_pack, mock_classify, mock_ocr, mock_ingest, dummy_invoice_pdf
):
    # Setup mocks
    mock_ingest.return_value = MagicMock(status=IngestionStatus.VALID, format=DocumentFormat.PDF, page_count=1)
    
    mock_ocr_result = MagicMock(status=IngestionStatus.VALID)
    mock_ocr_result.pages = [MagicMock(full_text="Invoice")]
    mock_ocr.return_value = mock_ocr_result
    
    prov = Provenance(source_file_sha256="test", tool_name="test", tool_version="1.0", parameters={})
    
    mock_class_record = EvidenceRecord(id=str(uuid.uuid4()), type="classification", status=EvidenceStatus.OK, observation={"document_type": DocumentType.INVOICE.value}, method="test", provenance=prov)
    mock_classify.return_value = mock_class_record
    
    mock_pack.return_value = MagicMock(invoice_date=MagicMock(value=None))
    mock_cons.return_value = [EvidenceRecord(id=str(uuid.uuid4()), type="invoice_consistency", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)]
    
    mock_meta_pdf.return_value = (None, [EvidenceRecord(id=str(uuid.uuid4()), type="forensic_metadata", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)])
    mock_pixels.return_value = (b"dummy", [EvidenceRecord(id=str(uuid.uuid4()), type="forensic_ela_region", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)])
    
    # Run
    bundle = run_pipeline(dummy_invoice_pdf)
    
    assert isinstance(bundle, EvidenceBundle)
    assert len(bundle.evidence) > 0
    types = [e.type for e in bundle.evidence]
    
    assert "ingestion" in types
    assert "text_extraction" in types
    assert "invoice_consistency" in types
    assert "forensic_metadata" in types
    
    # Pixel mock is called because it's a PDF
    mock_pixels.assert_called()

@patch("forgerylens.pipeline.ingest_document")
@patch("forgerylens.pipeline.extract_document_text")
@patch("forgerylens.pipeline.analyze_pdf")
@patch("forgerylens.pipeline.analyze_pixels")
def test_pipeline_dependency_failure(
    mock_pixels, mock_meta_pdf, mock_ocr, mock_ingest, dummy_invoice_pdf
):
    # Ingestion works
    mock_ingest.return_value = MagicMock(status=IngestionStatus.VALID, format=DocumentFormat.PDF, page_count=1)
    
    # OCR fails by returning an exception
    mock_ocr.side_effect = Exception("OCR Engine crashed")
    
    prov = Provenance(source_file_sha256="test", tool_name="test", tool_version="1.0", parameters={})
    mock_meta_pdf.return_value = (None, [EvidenceRecord(id=str(uuid.uuid4()), type="forensic_metadata", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)])
    mock_pixels.return_value = (None, [EvidenceRecord(id=str(uuid.uuid4()), type="forensic_image_analyzability", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)])
    
    bundle = run_pipeline(dummy_invoice_pdf)
    
    # Validate
    types = {e.type: e.status for e in bundle.evidence}
    
    # Ingestion was OK
    assert types.get("ingestion") == EvidenceStatus.OK
    
    # OCR failed, so it's NOT_ANALYZABLE
    assert types.get("text_extraction") == EvidenceStatus.NOT_ANALYZABLE
    
    # Classification is downstream, must be skipped/NOT_ANALYZABLE
    assert types.get("classification") == EvidenceStatus.NOT_ANALYZABLE
    
    # Invoice consistency not called / skipped because classification is NOT_ANALYZABLE
    assert "invoice_consistency" not in types
    
    # Metadata and pixels still ran
    assert types.get("forensic_metadata") == EvidenceStatus.OK
    assert mock_meta_pdf.called
    assert mock_pixels.called
