"""Tests for Phase 4 Structured Document Extraction."""

import pytest
from forgerylens.contracts.enums import IngestionStatus
from forgerylens.contracts.ocr import OCRResult, OCRPage, OCRWord, OCRExtractionMethod
from forgerylens.contracts.structured import DocumentType
from forgerylens.extraction.parser import parse_document

def _make_word(text: str, x: float, y: float, w: float=0.1, h: float=0.05) -> OCRWord:
    return OCRWord(text=text, confidence=99.0, x=x, y=y, width=w, height=h)

def test_extract_invoice_number_and_date():
    """Test extracting basic invoice fields."""
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="INVOICE NO: INV-2023-001\\nDate: 2023-10-01",
        words=[
            _make_word("INVOICE", 0.1, 0.1),
            _make_word("NO:", 0.2, 0.1),
            _make_word("INV-2023-001", 0.3, 0.1),
            _make_word("Date:", 0.1, 0.15),
            _make_word("2023-10-01", 0.2, 0.15),
        ]
    )
    result = OCRResult(document_id="doc1", pages=[page], status=IngestionStatus.VALID)
    
    invoice = parse_document(result)
    assert invoice.document_type == DocumentType.INVOICE
    assert invoice.invoice_number is not None
    assert invoice.invoice_number.raw_value == "INV-2023-001"
    assert invoice.invoice_number.region is not None
    assert invoice.invoice_number.region.page_number == 1
    
    assert invoice.invoice_date is not None
    assert invoice.invoice_date.raw_value == "2023-10-01"

def test_extract_vendor_and_customer():
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.TESSERACT_OCR,
        full_text="Tax Invoice\\nVendor: AutoFix Garage\\nBilled To: John Doe",
        words=[
            _make_word("Tax", 0.1, 0.1), _make_word("Invoice", 0.2, 0.1),
            _make_word("Vendor:", 0.1, 0.2), _make_word("AutoFix", 0.2, 0.2), _make_word("Garage", 0.3, 0.2),
            _make_word("Billed", 0.1, 0.3), _make_word("To:", 0.2, 0.3), _make_word("John", 0.3, 0.3), _make_word("Doe", 0.4, 0.3),
        ]
    )
    result = OCRResult(document_id="doc2", pages=[page], status=IngestionStatus.VALID)
    
    invoice = parse_document(result)
    assert invoice.vendor_name is not None
    assert invoice.vendor_name.raw_value == "AutoFix Garage"
    assert invoice.customer_name is not None
    assert invoice.customer_name.raw_value == "John Doe"

def test_extract_vehicle_and_claim():
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Invoice\\nVehicle No: MH-12-AB-1234\\nClaim No: CLM-999888\\nPolicy No: POL-112233\\nVIN: ABC1234567890XYZ",
        words=[
            _make_word("Invoice", 0.1, 0.1),
            _make_word("Vehicle", 0.1, 0.2), _make_word("No:", 0.2, 0.2), _make_word("MH-12-AB-1234", 0.3, 0.2),
            _make_word("Claim", 0.1, 0.3), _make_word("No:", 0.2, 0.3), _make_word("CLM-999888", 0.3, 0.3),
            _make_word("Policy", 0.1, 0.4), _make_word("No:", 0.2, 0.4), _make_word("POL-112233", 0.3, 0.4),
            _make_word("VIN:", 0.1, 0.5), _make_word("ABC1234567890XYZ", 0.2, 0.5),
        ]
    )
    result = OCRResult(document_id="doc3", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert invoice.vehicle_number is not None
    assert invoice.vehicle_number.raw_value == "MH-12-AB-1234"
    assert invoice.claim_number is not None
    assert invoice.claim_number.raw_value == "CLM-999888"
    assert invoice.policy_number is not None
    assert invoice.policy_number.raw_value == "POL-112233"
    assert invoice.vin_chassis_number is not None
    assert invoice.vin_chassis_number.raw_value == "ABC1234567890XYZ"

def test_extract_financials_and_missing_optional():
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Repair Bill\\nSubtotal: 10,000.00\\nTax 18%: 1,800.00\\nGrand Total: 11,800.00",
        words=[
            _make_word("Repair", 0.1, 0.1), _make_word("Bill", 0.2, 0.1),
            _make_word("Subtotal:", 0.1, 0.2), _make_word("10,000.00", 0.3, 0.2),
            _make_word("Tax", 0.1, 0.3), _make_word("18%:", 0.2, 0.3), _make_word("1,800.00", 0.3, 0.3),
            _make_word("Grand", 0.1, 0.4), _make_word("Total:", 0.2, 0.4), _make_word("11,800.00", 0.3, 0.4),
        ]
    )
    result = OCRResult(document_id="doc4", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert invoice.subtotal is not None
    assert invoice.subtotal.raw_value == "10,000.00"
    assert invoice.taxes is not None
    assert invoice.taxes.raw_value == "1,800.00"
    assert invoice.grand_total is not None
    assert invoice.grand_total.raw_value == "11,800.00"
    # Missing field
    assert invoice.discounts is None
    assert invoice.additional_charges is None

def test_extract_line_items():
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Invoice\\nDescription Qty Rate Amount\\nBrake Pad 2 2500 5000\\nOil Filter 1 1000 1000\\nSubtotal: 6000",
        words=[
            _make_word("Invoice", 0.1, 0.1),
            _make_word("Description", 0.1, 0.2), _make_word("Qty", 0.4, 0.2), _make_word("Rate", 0.6, 0.2), _make_word("Amount", 0.8, 0.2),
            _make_word("Brake", 0.1, 0.3), _make_word("Pad", 0.2, 0.3), _make_word("2", 0.4, 0.3), _make_word("2500", 0.6, 0.3), _make_word("5000", 0.8, 0.3),
            _make_word("Oil", 0.1, 0.4), _make_word("Filter", 0.2, 0.4), _make_word("1", 0.4, 0.4), _make_word("1000", 0.6, 0.4), _make_word("1000", 0.8, 0.4),
            _make_word("Subtotal:", 0.1, 0.5), _make_word("6000", 0.8, 0.5)
        ]
    )
    result = OCRResult(document_id="doc5", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert len(invoice.line_items) == 2
    item1 = invoice.line_items[0]
    assert item1.description.raw_value == "Brake Pad"
    assert item1.quantity.raw_value == "2"
    assert item1.unit_price.raw_value == "2500"
    assert item1.amount.raw_value == "5000"

    item2 = invoice.line_items[1]
    assert item2.description.raw_value == "Oil Filter"
    assert item2.quantity.raw_value == "1"

    # Explicit boundary check - we do NOT assert Phase 6 (math validation)

def test_multipage_invoice_extraction():
    page1 = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Invoice No: MULTI-123\\nVendor: Giant Corp",
        words=[
            _make_word("Invoice", 0.1, 0.1), _make_word("No:", 0.2, 0.1), _make_word("MULTI-123", 0.3, 0.1),
            _make_word("Vendor:", 0.1, 0.2), _make_word("Giant", 0.2, 0.2), _make_word("Corp", 0.3, 0.2)
        ]
    )
    page2 = OCRPage(
        page_number=2,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Grand Total: ₹ 1,00,000",
        words=[
            _make_word("Grand", 0.1, 0.1), _make_word("Total:", 0.2, 0.1), _make_word("₹", 0.3, 0.1), _make_word("1,00,000", 0.4, 0.1)
        ]
    )
    result = OCRResult(document_id="doc6", pages=[page1, page2], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert invoice.invoice_number.raw_value == "MULTI-123"
    assert invoice.invoice_number.region.page_number == 1
    
    assert invoice.grand_total.raw_value == "1,00,000"
    assert invoice.grand_total.region.page_number == 2

def test_unknown_document_type():
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Hello World\\nThis is just a random letter.",
        words=[
            _make_word("Hello", 0.1, 0.1), _make_word("World", 0.2, 0.1)
        ]
    )
    result = OCRResult(document_id="doc7", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert invoice.document_type == DocumentType.UNKNOWN
    # Fields should be missing
    assert invoice.invoice_number is None
    assert invoice.grand_total is None

def test_ambiguous_ocr_value_preserved():
    # If OCR output is weird, we preserve it. Phase 4 does not correct it.
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Invoice No: INV-2O45", # "O" instead of "0"
        words=[
            _make_word("Invoice", 0.1, 0.1), _make_word("No:", 0.2, 0.1), _make_word("INV-2O45", 0.3, 0.1)
        ]
    )
    result = OCRResult(document_id="doc8", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    assert invoice.invoice_number.raw_value == "INV-2O45"

def test_multiple_occurrences():
    # Tests that we can extract from a document with multiple total lines.
    # The first one that matches the pattern will be used by our parser.
    page = OCRPage(
        page_number=1,
        extraction_method=OCRExtractionMethod.NATIVE_PDF,
        full_text="Invoice\\nTotal: 50,000\\nGrand Total: 55,000",
        words=[
            _make_word("Invoice", 0.1, 0.1),
            _make_word("Total:", 0.1, 0.2), _make_word("50,000", 0.2, 0.2),
            _make_word("Grand", 0.1, 0.3), _make_word("Total:", 0.2, 0.3), _make_word("55,000", 0.3, 0.3)
        ]
    )
    result = OCRResult(document_id="doc9", pages=[page], status=IngestionStatus.VALID)
    invoice = parse_document(result)
    
    # Due to ordering in our patterns, "Grand Total" will match GRAND_TOTAL_PATTERNS
    assert invoice.grand_total is not None
    assert invoice.grand_total.raw_value == "55,000"
