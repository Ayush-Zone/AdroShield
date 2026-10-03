import re
from typing import Optional
from decimal import Decimal
from forgerylens.contracts.normalized import CurrencyAmount, NormalizedField, NormalizationStatus
from forgerylens.contracts.structured import FieldEvidence
from forgerylens.utils.numeric import parse_decimal

def normalize_numeric(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[Decimal]]:
    """Normalize a basic numeric value using a unified numeric parsing contract."""
    if not evidence:
        return None

    cands, errs = parse_decimal(evidence.raw_value)
    
    if len(cands) == 1:
        return NormalizedField.from_evidence(
            evidence,
            normalized_value=cands[0],
            status=NormalizationStatus.SUCCESS
        )
    elif len(cands) > 1:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=[f"Ambiguous numeric format in '{evidence.raw_value}'. Candidates: {[str(c) for c in cands]}"]
        )
    else:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=errs
        )

def normalize_currency(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[CurrencyAmount]]:
    """Normalize a string containing an amount and optional currency symbol."""
    if not evidence:
        return None
        
    raw_value = evidence.raw_value.strip()
    
    # Check for known currency symbols
    currency = None
    clean_val = raw_value
    
    # Matches INR, Rs, ₹, $
    inr_match = re.search(r"(?i)\bINR\b|\bRs\.?|₹", clean_val)
    if inr_match:
        currency = "INR"
        # Remove the currency part from the string
        clean_val = clean_val[:inr_match.start()] + clean_val[inr_match.end():]
        
    usd_match = re.search(r"\$", clean_val)
    if usd_match and not currency:
        currency = "USD"
        clean_val = clean_val[:usd_match.start()] + clean_val[usd_match.end():]
        
    cands, errs = parse_decimal(clean_val)
    
    if len(cands) == 1:
        return NormalizedField.from_evidence(
            evidence,
            normalized_value=CurrencyAmount(amount=cands[0], currency=currency),
            status=NormalizationStatus.SUCCESS
        )
    elif len(cands) > 1:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=[f"Ambiguous currency amount format in '{raw_value}'. Candidates: {[str(c) for c in cands]}"]
        )
    else:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=errs
        )
