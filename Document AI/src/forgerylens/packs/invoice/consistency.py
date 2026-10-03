import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
import uuid

from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance
from .models import ExtractedInvoicePack, FieldStatus, ExtractedField

def _parse_decimal(raw: str) -> Tuple[List[Decimal], List[str]]:
    """Parse a string to Decimal. Returns (valid_decimals, reasons).
    Handles ambiguous formats like 1,234.50 vs 1.234,50.
    """
    cleaned = re.sub(r'[^\d\.\,]', '', raw)
    if not cleaned:
        return [], ["Contains no digits"]
        
    candidates = set()
    
    # Format 1: 1,234.50 (comma as thousands, dot as decimal)
    # Also support commas only if there is no decimal point (e.g. 1,45,500)
    if '.' in cleaned or ',' not in cleaned or (',' in cleaned and (cleaned.rfind(',') < cleaned.rfind('.') or '.' not in cleaned)):
        try:
            val1 = cleaned.replace(',', '')
            candidates.add(Decimal(val1))
        except InvalidOperation:
            pass
            
    # Format 2: 1.234,50 (dot as thousands, comma as decimal) or 1.234 (dot as thousands)
    # Only treat dot as thousands if there are 3 digits after it, or if a comma is also present
    if ',' in cleaned or ('.' in cleaned and ',' not in cleaned and len(cleaned) - cleaned.rfind('.') == 4):
        try:
            val2 = cleaned.replace('.', '').replace(',', '.')
            candidates.add(Decimal(val2))
        except InvalidOperation:
            pass
            
    return list(candidates), [] if candidates else ["Could not parse as decimal"]

def _parse_date(raw: str) -> Tuple[List[date], List[str]]:
    """Parse date, returning candidates if ambiguous (e.g. 03/04/2026)."""
    candidates = set()
    raw = re.sub(r'[^\d\-\/]', '', raw)
    
    # ISO 2026-10-01
    try:
        candidates.add(datetime.strptime(raw, "%Y-%m-%d").date())
    except ValueError:
        pass
        
    # DD/MM/YYYY or MM/DD/YYYY
    parts = re.split(r'[\/\-]', raw)
    if len(parts) == 3:
        p1, p2, p3 = parts
        if len(p3) == 4:
            try:
                candidates.add(date(int(p3), int(p2), int(p1))) # DD/MM
            except ValueError:
                pass
            try:
                candidates.add(date(int(p3), int(p1), int(p2))) # MM/DD
            except ValueError:
                pass
                
    return list(candidates), [] if candidates else ["Could not parse as date"]

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

def check_subtotal_tax_vs_total(pack: ExtractedInvoicePack) -> EvidenceRecord:
    if pack.subtotal.status != FieldStatus.OK or pack.taxes.status != FieldStatus.OK or pack.grand_total.status != FieldStatus.OK:
        return _create_evidence("subtotal_tax_vs_total", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Missing or ambiguous input fields",
            "values_compared": {
                "subtotal": pack.subtotal.raw_value,
                "taxes": pack.taxes.raw_value,
                "grand_total": pack.grand_total.raw_value
            }
        })
        
    sub_cands, _ = _parse_decimal(pack.subtotal.raw_value)
    tax_cands, _ = _parse_decimal(pack.taxes.raw_value)
    tot_cands, _ = _parse_decimal(pack.grand_total.raw_value)
    
    if len(sub_cands) != 1 or len(tax_cands) != 1 or len(tot_cands) != 1:
        return _create_evidence("subtotal_tax_vs_total", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Ambiguous numerical formats",
            "candidates": {
                "subtotal": [str(x) for x in sub_cands],
                "taxes": [str(x) for x in tax_cands],
                "grand_total": [str(x) for x in tot_cands]
            }
        })
        
    sub = sub_cands[0]
    tax = tax_cands[0]
    tot = tot_cands[0]
    
    calc_total = sub + tax
    
    # Include explicit round-off / additional charges / discounts if extracted
    if pack.additional_charges.status == FieldStatus.OK:
        ac_cands, _ = _parse_decimal(pack.additional_charges.raw_value)
        if len(ac_cands) == 1:
            calc_total += ac_cands[0]
            
    if pack.discounts.status == FieldStatus.OK:
        dc_cands, _ = _parse_decimal(pack.discounts.raw_value)
        if len(dc_cands) == 1:
            calc_total -= dc_cands[0]
    
    diff = abs(calc_total - tot)
    tolerance = Decimal("0.02") # 0.01 per addend
    
    if diff == Decimal("0"):
        result = "exact"
    elif diff <= tolerance:
        result = "within_rounding"
    else:
        result = "mismatch"
        
    return _create_evidence("subtotal_tax_vs_total", EvidenceStatus.OK, {
        "result": result,
        "values_compared": {
            "subtotal": {"raw": pack.subtotal.raw_value, "parsed": str(sub)},
            "taxes": {"raw": pack.taxes.raw_value, "parsed": str(tax)},
            "grand_total": {"raw": pack.grand_total.raw_value, "parsed": str(tot)}
        },
        "computed_difference": str(diff),
        "tolerance": str(tolerance)
    })

def check_line_items_vs_subtotal(pack: ExtractedInvoicePack) -> EvidenceRecord:
    if not pack.line_items:
        return _create_evidence("line_items_vs_subtotal", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "input not extracted"
        })
    return _create_evidence("line_items_vs_subtotal", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Not implemented for non-empty line items"
    })

def check_tax_rate_vs_tax(pack: ExtractedInvoicePack) -> EvidenceRecord:
    return _create_evidence("tax_rate_vs_tax", EvidenceStatus.NOT_ANALYZABLE, {
        "reason": "input not extracted"
    })

def check_invoice_date(pack: ExtractedInvoicePack, reference_date: date) -> EvidenceRecord:
    if pack.invoice_date.status != FieldStatus.OK:
        return _create_evidence("invoice_date", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Missing or ambiguous input fields",
            "values_compared": {"invoice_date": pack.invoice_date.raw_value}
        })
        
    date_cands, _ = _parse_date(pack.invoice_date.raw_value)
    
    if len(date_cands) != 1:
        return _create_evidence("invoice_date", EvidenceStatus.NOT_ANALYZABLE, {
            "reason": "Ambiguous date formats",
            "candidates": {"invoice_date": [str(x) for x in date_cands]}
        })
        
    inv_date = date_cands[0]
    
    diff_days = (inv_date - reference_date).days
    
    if diff_days > 0:
        result = "mismatch"
    else:
        result = "exact"
        
    return _create_evidence("invoice_date", EvidenceStatus.OK, {
        "result": result,
        "values_compared": {
            "invoice_date": {"raw": pack.invoice_date.raw_value, "parsed": str(inv_date)},
            "reference_date": str(reference_date)
        },
        "computed_difference_days": diff_days,
        "tolerance": 0
    })

def run_all_consistency_checks(pack: ExtractedInvoicePack, reference_date: date) -> List[EvidenceRecord]:
    return [
        check_subtotal_tax_vs_total(pack),
        check_line_items_vs_subtotal(pack),
        check_tax_rate_vs_tax(pack),
        check_invoice_date(pack, reference_date)
    ]
