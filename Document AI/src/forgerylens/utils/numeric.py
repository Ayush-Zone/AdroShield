import re
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

def parse_decimal(raw: str) -> Tuple[List[Decimal], List[str]]:
    """Parse a string to Decimal. Returns (valid_decimals, reasons).
    Handles ambiguous formats like 1,234.50 vs 1.234,50.
    """
    if re.search(r'[a-zA-Z]', raw):
        return [], ["Contains alphabetic characters"]
    cleaned = re.sub(r'[^\d\.\,]', '', raw)
    if not cleaned:
        return [], ["Contains no digits"]
        
    candidates = set()
    
    # Format 1: 1,234.50 (comma as thousands, dot as decimal)
    # Also support commas only if there is no decimal point (e.g. 1,45,500)
    if '.' in cleaned or ',' not in cleaned or (',' in cleaned and (cleaned.rfind(',') < cleaned.rfind('.') or '.' not in cleaned)):
        try:
            val1 = cleaned.replace(',', '')
            d1 = Decimal(val1)
            candidates.add(d1.normalize())
        except InvalidOperation:
            pass
            
    # Format 2: 1.234,50 (dot as thousands, comma as decimal) or 1.234 (dot as thousands)
    # Only treat comma as decimal if it has exactly 2 or 1 digits after it, or if dot is also present before it.
    if ('.' in cleaned and ',' in cleaned and cleaned.rfind('.') < cleaned.rfind(',')) or \
       (',' in cleaned and '.' not in cleaned and len(cleaned) - cleaned.rfind(',') <= 3) or \
       ('.' in cleaned and ',' not in cleaned and len(cleaned) - cleaned.rfind('.') == 4):
        try:
            val2 = cleaned.replace('.', '').replace(',', '.')
            d2 = Decimal(val2)
            candidates.add(d2.normalize())
        except InvalidOperation:
            pass
            
    return sorted(list(candidates)), [] if candidates else ["Could not parse as decimal"]
