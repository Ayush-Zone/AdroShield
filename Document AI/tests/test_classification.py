import pytest
from forgerylens.classification.classifier import classify_document
from forgerylens.contracts.structured import DocumentType
from forgerylens.contracts.evidence import EvidenceStatus

def test_classify_clear_invoice():
    text = "TAX INVOICE\nVendor: MegaCorp\nQty: 1\nSubtotal: 100\nGrand Total: 110"
    record = classify_document(text)
    
    assert record.status == EvidenceStatus.OK
    assert record.observation["document_type"] == DocumentType.INVOICE.value
    assert len(record.observation["cues"]) >= 2
    assert "tax invoice" in record.observation["cues"]
    assert "subtotal" in record.observation["cues"]

def test_classify_id_document():
    text = "Name: John Doe\nDate of Birth: 01/01/1990\nPassport Number: A1234567\nNationality: USA"
    record = classify_document(text)
    
    assert record.status == EvidenceStatus.OK
    assert record.observation["document_type"] == DocumentType.ID_DOCUMENT.value
    assert "passport" in record.observation["cues"]
    assert "date of birth" in record.observation["cues"]

def test_classify_gibberish():
    text = "Hello world! This is a random text block with no specific domain words."
    record = classify_document(text)
    
    assert record.status == EvidenceStatus.OK
    assert record.observation["document_type"] == DocumentType.UNKNOWN.value
    assert record.observation["cues"] == {}

def test_classify_ambiguous():
    # Mix of medical and invoice
    text = "Apollo Hospital - Tax Invoice\nPatient: Jane Doe\nTreatment: Checkup\nGrand Total: 500"
    record = classify_document(text)
    
    assert record.status == EvidenceStatus.AMBIGUOUS
    assert record.observation["document_type"] == DocumentType.AMBIGUOUS.value
    assert "invoice" in record.observation["candidates"]
    assert "medical_bill" in record.observation["candidates"]
    
    # Should have recorded cues for both
    cues = record.observation["cues"]
    assert "tax invoice" in cues[DocumentType.INVOICE.value]
    assert "hospital" in cues[DocumentType.MEDICAL_BILL.value]
