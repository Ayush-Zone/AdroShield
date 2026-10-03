import re
from typing import Optional
from forgerylens.contracts.normalized import NormalizedField, NormalizationStatus
from forgerylens.contracts.structured import FieldEvidence


def normalize_text(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[str]]:
    """Clean up text fields (vendor name, customer name)."""
    if not evidence:
        return None
        
    raw_value = evidence.raw_value
    # Collapse multiple whitespaces and trim
    clean_val = re.sub(r"\s+", " ", raw_value).strip()
    
    if not clean_val:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=["Text normalization resulted in empty string"]
        )
        
    return NormalizedField.from_evidence(
        evidence,
        normalized_value=clean_val,
        status=NormalizationStatus.SUCCESS
    )


def normalize_identifier(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[str]]:
    """Clean up identifiers (invoice no, claim no, vehicle reg)."""
    if not evidence:
        return None
        
    raw_value = evidence.raw_value
    # Strip surrounding whitespace and convert to uppercase for consistency
    clean_val = raw_value.strip().upper()
    
    if not clean_val:
        return NormalizedField.from_evidence(
            evidence,
            status=NormalizationStatus.AMBIGUOUS,
            warnings=["Identifier normalization resulted in empty string"]
        )
        
    return NormalizedField.from_evidence(
        evidence,
        normalized_value=clean_val,
        status=NormalizationStatus.SUCCESS
    )
