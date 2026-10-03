import pytest
from forgerylens.contracts.structured import DocumentType, Region
from forgerylens.contracts.normalized import (
    NormalizedInvoice,
    NormalizedField,
    NormalizedLineItem,
    CurrencyAmount,
    NormalizationStatus
)
from forgerylens.validation.validator import validate_document
from forgerylens.contracts.validation import ValidationStatus, ValidationSeverity


def _make_field(val: float, raw: str = "raw") -> NormalizedField[CurrencyAmount]:
    return NormalizedField[CurrencyAmount](
        raw_value=raw,
        region=Region(page_number=1, x=0.0, y=0.0, width=0.1, height=0.1),
        normalized_value=CurrencyAmount(amount=val),
        status=NormalizationStatus.SUCCESS
    )

def _make_num_field(val: float, raw: str = "raw") -> NormalizedField[float]:
    return NormalizedField[float](
        raw_value=raw,
        region=Region(page_number=1, x=0.0, y=0.0, width=0.1, height=0.1),
        normalized_value=val,
        status=NormalizationStatus.SUCCESS
    )

def _make_str_field(val: str) -> NormalizedField[str]:
    return NormalizedField[str](
        raw_value=val,
        normalized_value=val,
        status=NormalizationStatus.SUCCESS
    )


def test_valid_invoice_arithmetic():
    invoice = NormalizedInvoice(
        document_id="doc1",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        subtotal=_make_field(100.00),
        taxes=_make_field(10.00),
        discounts=_make_field(5.00),
        additional_charges=_make_field(2.00),
        grand_total=_make_field(107.00),
        line_items=[
            NormalizedLineItem(
                quantity=_make_num_field(2.0),
                unit_price=_make_field(30.00),
                amount=_make_field(60.00)
            ),
            NormalizedLineItem(
                quantity=_make_num_field(1.0),
                unit_price=_make_field(40.00),
                amount=_make_field(40.00)
            )
        ]
    )
    
    result = validate_document(invoice)
    assert not result.has_critical_discrepancies
    # No MISSING, no UNABLE_TO_VERIFY (except expected cases), mostly VALID
    for finding in result.findings:
        assert finding.status == ValidationStatus.VALID


def test_incorrect_line_item_amount():
    invoice = NormalizedInvoice(
        document_id="doc2",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        grand_total=_make_field(100.00),
        line_items=[
            NormalizedLineItem(
                quantity=_make_num_field(2.0),
                unit_price=_make_field(30.00),
                amount=_make_field(70.00)  # Should be 60
            )
        ]
    )
    result = validate_document(invoice)
    assert result.has_critical_discrepancies
    findings = [f for f in result.findings if f.rule_name.startswith("line_item_arithmetic")]
    assert len(findings) == 1
    assert findings[0].status == ValidationStatus.INVALID
    assert findings[0].expected == "60.00"
    assert findings[0].observed == "70.00"
    assert findings[0].difference == "10.00"


def test_incorrect_subtotal():
    invoice = NormalizedInvoice(
        document_id="doc3",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        grand_total=_make_field(100.00),
        subtotal=_make_field(90.00), # Should be 100 based on line items
        line_items=[
            NormalizedLineItem(
                quantity=_make_num_field(2.0),
                unit_price=_make_field(50.00),
                amount=_make_field(100.00)
            )
        ]
    )
    result = validate_document(invoice)
    assert result.has_critical_discrepancies
    findings = [f for f in result.findings if f.rule_name == "subtotal_arithmetic"]
    assert len(findings) == 1
    assert findings[0].status == ValidationStatus.INVALID
    assert findings[0].expected == "100.00"
    assert findings[0].observed == "90.00"


def test_incorrect_grand_total():
    invoice = NormalizedInvoice(
        document_id="doc4",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        subtotal=_make_field(100.00),
        taxes=_make_field(18.00),
        grand_total=_make_field(110.00), # Should be 118.00
    )
    result = validate_document(invoice)
    assert result.has_critical_discrepancies
    findings = [f for f in result.findings if f.rule_name == "grand_total_arithmetic"]
    assert findings[0].status == ValidationStatus.INVALID
    assert findings[0].expected == "118.00"


def test_missing_required_field():
    invoice = NormalizedInvoice(
        document_id="doc5",
        document_type=DocumentType.INVOICE,
        # Missing invoice_number and invoice_date
        vendor_name=_make_str_field("Vendor"),
        grand_total=_make_field(100.00),
    )
    result = validate_document(invoice)
    findings = [f for f in result.findings if f.rule_name.startswith("required_field_")]
    missing = [f for f in findings if f.status == ValidationStatus.MISSING]
    assert len(missing) == 2


def test_ambiguous_numeric_field_and_unable_to_verify():
    subtotal = _make_field(100.00)
    subtotal.status = NormalizationStatus.AMBIGUOUS
    subtotal.normalized_value = None
    
    invoice = NormalizedInvoice(
        document_id="doc6",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        subtotal=subtotal,
        grand_total=_make_field(118.00),
        taxes=_make_field(18.00),
        line_items=[
            NormalizedLineItem(
                quantity=_make_num_field(2.0),
                unit_price=_make_field(50.00),
                amount=_make_field(100.00)
            )
        ]
    )
    result = validate_document(invoice)
    # Should not have critical discrepancy, just unable to verify
    assert not result.has_critical_discrepancies
    
    gt_finding = next(f for f in result.findings if f.rule_name == "grand_total_arithmetic")
    assert gt_finding.status == ValidationStatus.UNABLE_TO_VERIFY
    assert "ambiguous" in gt_finding.message
    
    sub_finding = next(f for f in result.findings if f.rule_name == "subtotal_arithmetic")
    assert sub_finding.status == ValidationStatus.UNABLE_TO_VERIFY


def test_partial_line_item_data():
    invoice = NormalizedInvoice(
        document_id="doc7",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        grand_total=_make_field(100.00),
        line_items=[
            NormalizedLineItem(
                quantity=None, # Missing quantity
                unit_price=_make_field(30.00),
                amount=_make_field(30.00)
            )
        ]
    )
    result = validate_document(invoice)
    # Line item arithmetic should skip silently if missing data
    li_findings = [f for f in result.findings if f.rule_name.startswith("line_item_arithmetic")]
    assert len(li_findings) == 0


def test_legitimate_rounding_behavior():
    invoice = NormalizedInvoice(
        document_id="doc8",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        grand_total=_make_field(100.00),
        line_items=[
            NormalizedLineItem(
                quantity=_make_num_field(3.0),
                unit_price=_make_field(33.33),
                amount=_make_field(100.00) # 3 * 33.33 = 99.99, difference is 0.01
            )
        ]
    )
    result = validate_document(invoice)
    assert not result.has_critical_discrepancies
    li_finding = next(f for f in result.findings if f.rule_name.startswith("line_item_arithmetic"))
    assert li_finding.status == ValidationStatus.VALID


def test_provenance_preservation():
    invoice = NormalizedInvoice(
        document_id="doc9",
        document_type=DocumentType.INVOICE,
        invoice_number=_make_str_field("INV-001"),
        invoice_date=_make_str_field("2026-01-01"),
        vendor_name=_make_str_field("Vendor"),
        subtotal=_make_field(100.00, "100.00"),
        taxes=_make_field(18.00, "18.00"),
        grand_total=_make_field(200.00, "200.00"), # Error
    )
    result = validate_document(invoice)
    gt_finding = next(f for f in result.findings if f.rule_name == "grand_total_arithmetic")
    assert gt_finding.status == ValidationStatus.INVALID
    assert "subtotal" in gt_finding.involved_fields
    assert "taxes" in gt_finding.involved_fields
    assert "grand_total" in gt_finding.involved_fields
    
    # Check region/raw_value preservation
    assert gt_finding.involved_fields["subtotal"]["raw_value"] == "100.00"
    assert gt_finding.involved_fields["subtotal"]["region"]["page_number"] == 1
