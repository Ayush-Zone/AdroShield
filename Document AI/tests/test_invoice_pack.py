import pytest
from forgerylens.contracts.ocr import OCRResult, OCRPage, OCRWord
from forgerylens.packs.invoice import extract_invoice_pack, FieldStatus

def _create_mock_ocr_result(text_lines):
    words = []
    y_pos = 0.1
    for line in text_lines:
        x_pos = 0.1
        for word_text in line.split():
            words.append(
                OCRWord(
                    text=word_text,
                    confidence=95.0,
                    x=x_pos,
                    y=y_pos,
                    width=0.05,
                    height=0.02
                )
            )
            x_pos += 0.06
        y_pos += 0.03
        
    page = OCRPage(page_number=1, words=words, full_text="\n".join(text_lines), extraction_method="tesseract_ocr")
    return OCRResult(
        document_id="doc1",
        method="test",
        status="valid",
        pages=[page]
    )

def test_invoice_pack_known_fields():
    lines = [
        "Invoice No: INV-1234",
        "Date: 2026-10-01",
        "Subtotal: $100.00",
        "Tax: $10.00",
        "Grand Total: $110.00"
    ]
    ocr_result = _create_mock_ocr_result(lines)
    pack = extract_invoice_pack(ocr_result)
    
    assert pack.invoice_number.status == FieldStatus.OK
    assert pack.invoice_number.raw_value == "INV-1234"
    assert pack.invoice_number.region is not None
    assert pack.invoice_number.region.page_number == 1
    
    assert pack.invoice_date.status == FieldStatus.OK
    assert pack.invoice_date.raw_value == "2026-10-01"
    
    assert pack.subtotal.status == FieldStatus.OK
    assert pack.subtotal.raw_value == "$100.00"
    
    assert pack.taxes.status == FieldStatus.OK
    assert pack.taxes.raw_value == "$10.00"
    
    assert pack.grand_total.status == FieldStatus.OK
    assert pack.grand_total.raw_value == "$110.00"
    assert pack.grand_total.region is not None

def test_invoice_pack_missing_total():
    lines = [
        "Invoice No: INV-1234",
        "Date: 2026-10-01",
        "Subtotal: $100.00"
    ]
    ocr_result = _create_mock_ocr_result(lines)
    pack = extract_invoice_pack(ocr_result)
    
    assert pack.grand_total.status == FieldStatus.MISSING
    assert pack.grand_total.raw_value is None
    assert pack.grand_total.region is None
    assert "No regex patterns matched" in pack.grand_total.reason

def test_invoice_pack_ambiguous_dates():
    # Two dates present on different lines, both matching the date pattern
    lines = [
        "Invoice No: INV-1234",
        "Date: 03/04/2026",
        "Date: 15/04/2026",
        "Grand Total: $110.00"
    ]
    ocr_result = _create_mock_ocr_result(lines)
    pack = extract_invoice_pack(ocr_result)
    
    assert pack.invoice_date.status == FieldStatus.AMBIGUOUS
    assert pack.invoice_date.raw_value is None
    assert pack.invoice_date.region is None
    assert pack.invoice_date.candidates is not None
    assert len(pack.invoice_date.candidates) == 2
    
    c1 = pack.invoice_date.candidates[0]
    c2 = pack.invoice_date.candidates[1]
    
    assert c1.raw_value == "03/04/2026"
    assert c2.raw_value == "15/04/2026"
    assert c1.region is not None
    assert c2.region is not None
