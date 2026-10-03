import pytest
from forgerylens.contracts.structured import (
    DocumentType,
    FieldEvidence,
    InvoiceLineItem,
    StructuredInvoice,
    Region,
)
from forgerylens.contracts.normalized import (
    NormalizationStatus,
    CurrencyAmount,
)
from forgerylens.normalization.normalizer import normalize_document
from forgerylens.normalization.currency import normalize_currency, normalize_numeric
from forgerylens.normalization.dates import normalize_date
from forgerylens.normalization.text import normalize_identifier, normalize_text


def _make_evidence(val: str) -> FieldEvidence:
    return FieldEvidence(
        raw_value=val,
        region=Region(page_number=1, x=0.1, y=0.1, width=0.1, height=0.1)
    )

def test_normalize_currency_inr():
    # Test common INR formats
    assert normalize_currency(_make_evidence("85,000")).normalized_value == CurrencyAmount(amount=85000.0, currency=None)
    
    inr_res = normalize_currency(_make_evidence("₹ 85,000.00"))
    assert inr_res.normalized_value == CurrencyAmount(amount=85000.0, currency="INR")
    assert inr_res.status == NormalizationStatus.SUCCESS
    
    inr_res_2 = normalize_currency(_make_evidence("INR 85000"))
    assert inr_res_2.normalized_value == CurrencyAmount(amount=85000.0, currency="INR")
    
    inr_res_3 = normalize_currency(_make_evidence("Rs. 1,500.50"))
    assert inr_res_3.normalized_value == CurrencyAmount(amount=1500.5, currency="INR")

def test_normalize_currency_ambiguous():
    amb_res = normalize_currency(_make_evidence("₹B5,000"))
    assert amb_res.status == NormalizationStatus.AMBIGUOUS
    assert amb_res.normalized_value is None
    assert amb_res.raw_value == "₹B5,000"
    assert len(amb_res.warnings) > 0

def test_normalize_numeric():
    assert normalize_numeric(_make_evidence("85,000")).normalized_value == 85000.0
    assert normalize_numeric(_make_evidence("85,000.50")).normalized_value == 85000.5
    assert normalize_numeric(_make_evidence("abc")).status == NormalizationStatus.AMBIGUOUS

def test_normalize_date():
    assert normalize_date(_make_evidence("12/09/2026")).normalized_value == "2026-09-12"
    assert normalize_date(_make_evidence("12-09-2026")).normalized_value == "2026-09-12"
    assert normalize_date(_make_evidence("12 Sep 2026")).normalized_value == "2026-09-12"
    assert normalize_date(_make_evidence("2026-10-01")).normalized_value == "2026-10-01"
    
    amb_date = normalize_date(_make_evidence("Some ambiguous date"))
    assert amb_date.status == NormalizationStatus.AMBIGUOUS
    assert amb_date.normalized_value is None

def test_normalize_text_and_identifier():
    assert normalize_text(_make_evidence("  Hello   World  ")).normalized_value == "Hello World"
    assert normalize_identifier(_make_evidence("  abC-123  ")).normalized_value == "ABC-123"
    
    empty_res = normalize_text(_make_evidence("   "))
    assert empty_res.status == NormalizationStatus.AMBIGUOUS

def test_normalize_document():
    invoice = StructuredInvoice(
        document_id="doc-123",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_evidence(" INV-100 "),
        invoice_date=_make_evidence("15 Oct 2023"),
        vendor_name=_make_evidence("  Super   Vendor  "),
        subtotal=_make_evidence("10,000"),
        taxes=_make_evidence("₹ 1,800.50"),
        grand_total=_make_evidence("Invalid Amount"),
        line_items=[
            InvoiceLineItem(
                description=_make_evidence("Service A"),
                quantity=_make_evidence("2"),
                unit_price=_make_evidence("5,000"),
                amount=_make_evidence("10,000")
            ),
            InvoiceLineItem(
                description=_make_evidence("Empty line")
            )
        ]
    )
    
    normalized = normalize_document(invoice)
    
    # Check top level
    assert normalized.document_id == "doc-123"
    assert normalized.document_type == DocumentType.INVOICE
    
    # Check basic fields
    assert normalized.invoice_number.normalized_value == "INV-100"
    assert normalized.invoice_number.raw_value == " INV-100 "
    assert normalized.invoice_date.normalized_value == "2023-10-15"
    assert normalized.vendor_name.normalized_value == "Super Vendor"
    
    # Check financial fields
    assert normalized.subtotal.normalized_value == CurrencyAmount(amount=10000.0, currency=None)
    assert normalized.taxes.normalized_value == CurrencyAmount(amount=1800.5, currency="INR")
    assert normalized.grand_total.status == NormalizationStatus.AMBIGUOUS
    assert normalized.grand_total.normalized_value is None
    
    # Check provenance
    assert normalized.invoice_number.region.page_number == 1
    
    # Missing fields should remain missing
    assert normalized.customer_name is None
    
    # Line items
    assert len(normalized.line_items) == 2
    assert normalized.line_items[0].quantity.normalized_value == 2.0
    assert normalized.line_items[0].unit_price.normalized_value == CurrencyAmount(amount=5000.0, currency=None)
    
    # Empty line item
    assert normalized.line_items[1].description.normalized_value == "Empty line"
    assert normalized.line_items[1].quantity is None
