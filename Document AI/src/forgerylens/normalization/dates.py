import re
from datetime import datetime
from typing import Optional
from forgerylens.contracts.normalized import NormalizedField, NormalizationStatus
from forgerylens.contracts.structured import FieldEvidence


def normalize_date(evidence: Optional[FieldEvidence]) -> Optional[NormalizedField[str]]:
    """Normalize a date string to ISO format YYYY-MM-DD."""
    if not evidence:
        return None

    raw_value = evidence.raw_value.strip()
    
    # Define common formats
    # 1. YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    match_ymd = re.match(r"^(\d{4})[\-/\.](\d{1,2})[\-/\.](\d{1,2})$", raw_value)
    if match_ymd:
        try:
            dt = datetime(int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3)))
            return _success(evidence, dt)
        except ValueError:
            pass
            
    # 2. DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
    match_dmy = re.match(r"^(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{4})$", raw_value)
    if match_dmy:
        try:
            # Need to be careful. Is it MM-DD-YYYY or DD-MM-YYYY?
            # Standard assumption for this project is often DD-MM-YYYY, but 
            # if unambiguous, we parse.
            d, m, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
            if m > 12:
                # Must be MM-DD-YYYY
                m, d = d, m
            dt = datetime(y, m, d)
            return _success(evidence, dt)
        except ValueError:
            pass

    # 3. DD MMM YYYY (e.g. 12 Sep 2026)
    try:
        # Note: strptime "%d %b %Y" handles short month names
        dt = datetime.strptime(re.sub(r"[\s\,]+", " ", raw_value).strip(), "%d %b %Y")
        return _success(evidence, dt)
    except ValueError:
        pass
        
    try:
        dt = datetime.strptime(re.sub(r"[\s\,]+", " ", raw_value).strip(), "%d %B %Y")
        return _success(evidence, dt)
    except ValueError:
        pass
        
    # If all parsing fails, return ambiguous
    return NormalizedField.from_evidence(
        evidence,
        status=NormalizationStatus.AMBIGUOUS,
        warnings=[f"Could not unambiguously parse date '{raw_value}'"]
    )

def _success(evidence: FieldEvidence, dt: datetime) -> NormalizedField[str]:
    return NormalizedField.from_evidence(
        evidence,
        normalized_value=dt.strftime("%Y-%m-%d"),
        status=NormalizationStatus.SUCCESS
    )
