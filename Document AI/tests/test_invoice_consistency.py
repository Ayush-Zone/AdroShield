import pytest
from datetime import date
from forgerylens.contracts.normalized import NormalizedInvoice, NormalizedField, NormalizationStatus, CurrencyAmount
from forgerylens.packs.invoice.consistency import run_all_consistency_checks
from forgerylens.contracts.evidence import EvidenceStatus
from forgerylens.contracts.structured import DocumentType
from decimal import Decimal

def _make_field(val: str, status=NormalizationStatus.SUCCESS):
    return NormalizedField(
        raw_value=val,
        status=status,
        normalized_value=CurrencyAmount(amount=Decimal(val), currency="USD") if status == NormalizationStatus.SUCCESS and val else None
    )

def _make_date_field(val: str, status=NormalizationStatus.SUCCESS):
    return NormalizedField(
        raw_value=val,
        status=status,
        normalized_value=val if status == NormalizationStatus.SUCCESS else None
    )

def _make_pack(sub="100.00", tax="10.00", total="110.00", inv_date="2026-10-01"):
    return NormalizedInvoice(
        document_id="test",
        document_type=DocumentType.INVOICE,
        invoice_number=NormalizedField(raw_value="INV-1", status=NormalizationStatus.SUCCESS, normalized_value="INV-1"),
        invoice_date=_make_date_field(inv_date),
        vendor_name=NormalizedField(raw_value="Vendor", status=NormalizationStatus.SUCCESS, normalized_value="Vendor"),
        customer_name=NormalizedField(raw_value="Cust", status=NormalizationStatus.SUCCESS, normalized_value="Cust"),
        subtotal=_make_field(sub),
        taxes=_make_field(tax),
        grand_total=_make_field(total),
        line_items=[]
    )

def test_exact_match():
    pack = _make_pack(sub="100.00", tax="10.00", total="110.00")
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))

    # Subtotal check
    ev = checks[0]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "exact"
    assert ev.observation["computed_difference"] == "0.00"

def test_within_rounding():
    # diff is 0.02, tolerance is 0.02
    pack = _make_pack(sub="100.01", tax="10.00", total="110.03")
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[0]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "within_rounding"
    assert ev.observation["computed_difference"] == "0.02"

def test_mismatch_boundary():
    # diff is 0.03, tolerance is 0.02 -> mismatch
    pack = _make_pack(sub="100.01", tax="10.00", total="110.04")
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[0]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "mismatch"
    assert ev.observation["computed_difference"] == "0.03"
    assert ev.observation["values_compared"]["subtotal"]["parsed"] == "100.01"
    assert ev.observation["values_compared"]["grand_total"]["parsed"] == "110.04"

def test_round_off_line():
    pack = _make_pack(sub="100.00", tax="10.00", total="110.05")
    # Sub + Tax = 110.00, Total = 110.05 -> mismatch
    # Add round-off line (additional charges)
    pack.additional_charges = _make_field("0.05")
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[0]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "exact"
    assert ev.observation["computed_difference"] == "0.00"

def test_missing_field():
    pack = _make_pack()
    pack.grand_total = None
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[0]
    assert ev.status == EvidenceStatus.NOT_ANALYZABLE
    assert "Missing or ambiguous" in ev.observation["reason"]

def test_ambiguous_number():
    # 1.234,50 and 1,234.50 are both valid numbers if only one is present,
    pack = _make_pack(tax="10.00", total="110.00")
    pack.subtotal = _make_field("1.234", NormalizationStatus.AMBIGUOUS)
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[0]
    assert ev.status == EvidenceStatus.NOT_ANALYZABLE
    assert "Ambiguous numerical formats" in ev.observation["reason"]

def test_ambiguous_date():
    pack = _make_pack()
    pack.invoice_date = _make_date_field("03/04/2026", NormalizationStatus.AMBIGUOUS)
    checks = run_all_consistency_checks(pack, date(2026, 10, 2))
    ev = checks[3] # invoice_date check
    assert ev.status == EvidenceStatus.NOT_ANALYZABLE
    assert "Ambiguous date formats" in ev.observation["reason"]

def test_future_date():
    pack = _make_pack(inv_date="2026-12-01")
    checks = run_all_consistency_checks(pack, date(2026, 10, 1))
    ev = checks[3]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "mismatch"
    assert ev.observation["computed_difference_days"] > 0

def test_decimal_vs_float():
    pack = _make_pack(sub="0.10", tax="0.20", total="0.30")
    checks = run_all_consistency_checks(pack, date(2026, 10, 1))
    ev = checks[0]
    assert ev.status == EvidenceStatus.OK
    assert ev.observation["result"] == "exact"
    assert ev.observation["computed_difference"] == "0.00"

def test_input_not_extracted():
    pack = _make_pack()
    checks = run_all_consistency_checks(pack, date(2026, 10, 1))
    # line items
    assert checks[1].status == EvidenceStatus.NOT_ANALYZABLE
    assert checks[1].observation["reason"] == "input not extracted"
    # tax rate
    assert checks[2].status == EvidenceStatus.NOT_ANALYZABLE
    assert checks[2].observation["reason"] == "input not extracted"
