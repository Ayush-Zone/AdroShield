import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PIL import Image
import json
import uuid

from forgerylens.contracts.evidence import EvidenceBundle, EvidenceRecord, EvidenceStatus, Provenance, EvidenceLocation
from forgerylens.demo_hook import generate_demo_ui_payload
from forgerylens.contracts.storage import resolve_artifact_ref
from forgerylens.contracts.enums import IngestionStatus, DocumentFormat
from forgerylens.pipeline import run_pipeline

@pytest.fixture
def test_bundle():
    prov = Provenance(source_file_sha256="testhash", tool_name="test", tool_version="1.0", parameters={})
    
    obs_ela = {
        "raw_difference_magnitude": 1500.5,
        "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    }
    ela_record = EvidenceRecord(
        id="rec_ela",
        type="forensic_ela_region",
        status=EvidenceStatus.OK,
        observation=obs_ela,
        method="pixel_analysis",
        provenance=prov,
        raw_ref="artifact:1234567890123456789012345678901234567890123456789012345678901234/ela_map.png",
        confidence=None,
        limitations="weak indicator only"
    )
    
    obs_cons = {
        "result": "mismatch",
        "status": "invalid"
    }
    cons_record = EvidenceRecord(
        id="rec_cons",
        type="consistency_check_test",
        status=EvidenceStatus.AMBIGUOUS,
        observation=obs_cons,
        method="rule_based",
        provenance=prov,
        location=EvidenceLocation(page_number=1, x=0.1, y=0.1, width=0.1, height=0.1)
    )
    
    not_analyzable_record = EvidenceRecord(
        id="rec_na",
        type="forensic_ela_applicability",
        status=EvidenceStatus.NOT_ANALYZABLE,
        observation={"reasons": ["no JPEG compression history (PDF input)"]},
        method="rule_based",
        provenance=prov
    )
    
    bundle = EvidenceBundle(
        id="bundle_1",
        document_provenance=prov,
        evidence=[ela_record, cons_record, not_analyzable_record],
        findings=[]
    )
    return bundle

def validate_payload(payload):
    payload_str = json.dumps(payload).lower()
    for forbidden in ["suspicious_score", "risk", "verdict"]:
        assert forbidden not in payload_str
        
    assert "c:\\" not in payload_str
    assert "/users/" not in payload_str
    assert "file:" not in payload_str
    
    evidence_ids = {e["id"] for e in payload["evidence"]}
    for f in payload["findings"]:
        for eid in f["evidence_ids"]:
            assert eid in evidence_ids

def test_payload_format(test_bundle):
    payload = generate_demo_ui_payload(test_bundle)
    validate_payload(payload)
    
    na_rec = next(e for e in payload["evidence"] if e["id"] == "rec_na")
    assert na_rec["status"] == "not_analyzable"
    
    cons_rec = next(e for e in payload["evidence"] if e["id"] == "rec_cons")
    assert cons_rec["status"] == "ambiguous"
    assert cons_rec["location"]["x"] == 0.1
    assert cons_rec["location"]["width"] == 0.1
    
def test_no_findings():
    prov = Provenance(source_file_sha256="testhash", tool_name="test", tool_version="1.0", parameters={})
    bundle = EvidenceBundle(
        id="bundle_2",
        document_provenance=prov,
        evidence=[],
        findings=[]
    )
    payload = generate_demo_ui_payload(bundle)
    assert len(payload["findings"]) == 0

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

@pytest.fixture
def dummy_jpeg(tmp_path):
    path = tmp_path / "test.jpg"
    import numpy as np
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    img.save(path, format="JPEG")
    return str(path)

@patch("forgerylens.pipeline.extract_document_text")
@patch("forgerylens.pipeline.classify_document")
def test_payload_pdf_and_jpeg(mock_class, mock_ocr, dummy_invoice_pdf, dummy_jpeg):
    page_mock = MagicMock(full_text="Invoice")
    page_mock.page_number = 1
    page_mock.extraction_method.value = "mocked"
    mock_ocr.return_value = MagicMock(status=IngestionStatus.VALID, pages=[page_mock])
    prov = Provenance(source_file_sha256="test", tool_name="test", tool_version="1.0", parameters={})
    mock_class.return_value = EvidenceRecord(id=str(uuid.uuid4()), type="classification", status=EvidenceStatus.OK, observation={"document_type": "invoice"}, method="test", provenance=prov)
    
    # PDF
    bundle_pdf = run_pipeline(dummy_invoice_pdf)
    payload_pdf = generate_demo_ui_payload(bundle_pdf)
    validate_payload(payload_pdf)
    
    # Check that refs resolve
    for e in payload_pdf["evidence"]:
        if e["raw_ref"]:
            assert resolve_artifact_ref(e["raw_ref"], Path("/tmp")) is not None
    
    # JPEG
    bundle_jpeg = run_pipeline(dummy_jpeg)
    payload_jpeg = generate_demo_ui_payload(bundle_jpeg)
    validate_payload(payload_jpeg)
    
    # Check that refs resolve
    for e in payload_jpeg["evidence"]:
        if e["raw_ref"]:
            assert resolve_artifact_ref(e["raw_ref"], Path("/tmp")) is not None

