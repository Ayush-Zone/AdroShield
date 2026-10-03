from decimal import Decimal
from datetime import date
from typing import List, Dict, Any
import uuid

from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance
from forgerylens.contracts.normalized import NormalizedInvoice, NormalizationStatus

def _create_evidence(check_name: str, status: EvidenceStatus, observation: Dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(uuid.uuid4()),
        type=f"consistency_check_{check_name}",
        observation=observation,
        method="rule_based",
        status=status,
        provenance=Provenance(
            source_file_sha256="unknown",
            tool_name="forgerylens_consistency",
            tool_version="1.0",
            parameters={"check": check_name}
        )
    )

def check_subtotal_tax_vs_total(invoice: NormalizedInvoice) -> EvidenceRecord:
    sub = invoice.subtotal
    tax = invoice.taxes
    tot = invoice.grand_total

    if not sub or not tax or not tot or sub.status != NormalizationStatus.SUCCESS or tax.status != NormalizationStatus.SUCCESS or tot.status != NormalizationStatus.SUCCESS:
        reason = "Ambiguous numerical formats" if (
            (sub and sub.status == NormalizationStatus.AMBIGUOUS) or
            (tax and tax.status == NormalizationStatus.AMBIGUOUS) or
            (tot and tot.status == NormalizationStatus.AMBIGUOUS)
        ) else "Missing or ambiguous input fields"
        return _create_evidence("subtotal_tax_vs_total", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": reason,
            "values_compared": {
                "subtotal": sub.raw_value if sub else None,
                "taxes": tax.raw_value if tax else None,
                "grand_total": tot.raw_value if tot else None
            }
        })

    sub_val = sub.normalized_value.amount
    tax_val = tax.normalized_value.amount
    tot_val = tot.normalized_value.amount

    calc_total = sub_val + tax_val

    if invoice.additional_charges and invoice.additional_charges.status == NormalizationStatus.SUCCESS:
        calc_total += invoice.additional_charges.normalized_value.amount

    if invoice.discounts and invoice.discounts.status == NormalizationStatus.SUCCESS:
        calc_total -= invoice.discounts.normalized_value.amount

    diff = abs(calc_total - tot_val)
    tolerance = Decimal("0.02")

    if diff == Decimal("0"):
        result = "exact"
    elif diff <= tolerance:
        result = "within_rounding"
    else:
        result = "mismatch"

    return _create_evidence("subtotal_tax_vs_total", EvidenceStatus.OK, {
        "result": result,
        "values_compared": {
            "subtotal": {"raw": sub.raw_value, "parsed": str(sub_val)},
            "taxes": {"raw": tax.raw_value, "parsed": str(tax_val)},
            "grand_total": {"raw": tot.raw_value, "parsed": str(tot_val)}
        },
        "computed_difference": str(diff),
        "tolerance": str(tolerance)
    })

def check_line_items_vs_subtotal(invoice: NormalizedInvoice) -> EvidenceRecord:
    if not invoice.line_items:
        return _create_evidence("line_items_vs_subtotal", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "input not extracted"
        })

    sub = invoice.subtotal
    if not sub or sub.status != NormalizationStatus.SUCCESS:
        return _create_evidence("line_items_vs_subtotal", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Missing or ambiguous subtotal"
        })

    calc_subtotal = Decimal("0")
    for item in invoice.line_items:
        if not item.amount or item.amount.status != NormalizationStatus.SUCCESS:
            return _create_evidence("line_items_vs_subtotal", EvidenceStatus.NOT_ANALYZABLE, {
                "reason": "Ambiguous or unparseable amount in line item",
                "raw_value": item.amount.raw_value if item.amount else None
            })
        calc_subtotal += item.amount.normalized_value.amount

    sub_val = sub.normalized_value.amount
    diff = abs(calc_subtotal - sub_val)
    tolerance = Decimal("0.02")

    if diff == Decimal("0"):
        result = "exact"
    elif diff <= tolerance:
        result = "within_rounding"
    else:
        result = "mismatch"

    return _create_evidence("line_items_vs_subtotal", EvidenceStatus.OK, {
        "result": result,
        "values_compared": {
            "calculated_line_items_sum": str(calc_subtotal),
            "subtotal": {"raw": sub.raw_value, "parsed": str(sub_val)}
        },
        "computed_difference": str(diff),
        "tolerance": str(tolerance)
    })

def check_tax_rate_vs_tax(invoice: NormalizedInvoice) -> EvidenceRecord:
    return _create_evidence("tax_rate_vs_tax", EvidenceStatus.NOT_ANALYZABLE, {
        "reason": "input not extracted"
    })

def check_invoice_date(invoice: NormalizedInvoice, reference_date: date | None) -> EvidenceRecord:
    if reference_date is None:
        return _create_evidence("invoice_date", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "no reference date supplied"
        })

    inv_date_field = invoice.invoice_date
    if not inv_date_field or inv_date_field.status != NormalizationStatus.SUCCESS:
        reason = "Ambiguous date formats" if inv_date_field and inv_date_field.status == NormalizationStatus.AMBIGUOUS else "Missing or ambiguous input fields"
        return _create_evidence("invoice_date", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": reason,
            "values_compared": {"invoice_date": inv_date_field.raw_value if inv_date_field else None}
        })

    inv_date = date.fromisoformat(inv_date_field.normalized_value)

    diff_days = (inv_date - reference_date).days

    if diff_days > 0:
        result = "mismatch"
    else:
        result = "exact"

    return _create_evidence("invoice_date", EvidenceStatus.OK, {
        "result": result,
        "values_compared": {
            "invoice_date": {"raw": inv_date_field.raw_value, "parsed": str(inv_date)},
            "reference_date": str(reference_date)
        },
        "computed_difference_days": diff_days,
        "tolerance": 0
    })

def run_all_consistency_checks(invoice: NormalizedInvoice, reference_date: date | None) -> List[EvidenceRecord]:
    return [
        check_subtotal_tax_vs_total(invoice),
        check_line_items_vs_subtotal(invoice),
        check_tax_rate_vs_tax(invoice),
        check_invoice_date(invoice, reference_date)
    ]
