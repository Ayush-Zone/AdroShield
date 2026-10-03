import re
from typing import Optional, Tuple
from forgerylens.contracts.normalized import CurrencyAmount, NormalizedField, NormalizationStatus
from forgerylens.contracts.structured import FieldEvidence


def normalize_numeric(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[float]]:
    """Normalize a basic numeric value (integer or float)."""
    if not evidence:
        return None

    raw_value = evidence.raw_value.strip()
    
    # Remove commas and spaces
    clean_val = re.sub(r"[,\s]", "", raw_value)
    
    try:
        parsed_val = float(clean_val)
        return NormalizedField.from_evidence(
            evidence,
            normalized_value=parsed_val,
            status=NormalizationStatus.SUCCESS
        )
    except ValueError:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=[f"Could not parse '{raw_value}' as a number"]
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
        
    # Clean the numeric part
    clean_val = re.sub(r"[,\s]", "", clean_val)
    
    try:
        parsed_amount = float(clean_val)
        return NormalizedField.from_evidence(
            evidence,
            normalized_value=CurrencyAmount(amount=parsed_amount, currency=currency),
            status=NormalizationStatus.SUCCESS
        )
    except ValueError:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=[f"Could not parse '{raw_value}' as a currency amount"]
        )
