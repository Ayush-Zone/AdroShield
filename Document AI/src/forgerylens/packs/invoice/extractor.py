import re
from typing import List

from forgerylens.contracts.ocr import OCRResult, OCRWord, OCRPage
from forgerylens.contracts.structured import Region
from .models import ExtractedField, FieldStatus, ExtractedInvoicePack, ExtractedLineItem

class TextLine:
    """Helper class representing a horizontal line of text."""
    def __init__(self, page_num: int):
        self.page_number = page_num
        self.words: List[OCRWord] = []
        
    def add_word(self, word: OCRWord):
        self.words.append(word)
        self.words.sort(key=lambda w: w.x)
        
    @property
    def text(self) -> str:
        return " ".join([w.text for w in self.words])
        
    @property
    def region(self) -> Region:
        if not self.words:
            return Region(page_number=self.page_number, x=0, y=0, width=0, height=0)
        x_min = min(w.x for w in self.words)
        y_min = min(w.y for w in self.words)
        x_max = max(w.x + w.width for w in self.words)
        y_max = max(w.y + w.height for w in self.words)
        return Region(
            page_number=self.page_number,
            x=x_min,
            y=y_min,
            width=x_max - x_min,
            height=y_max - y_min
        )

def _group_words_into_lines(page: OCRPage, y_tolerance: float = 0.015) -> List[TextLine]:
    lines: List[TextLine] = []
    sorted_words = sorted(page.words, key=lambda w: (w.y, w.x))
    
    for word in sorted_words:
        matched_line = None
        for line in lines:
            line_y_min = min(w.y for w in line.words)
            if abs(word.y - line_y_min) <= y_tolerance:
                matched_line = line
                break
                
        if matched_line:
            matched_line.add_word(word)
        else:
            new_line = TextLine(page.page_number)
            new_line.add_word(word)
            lines.append(new_line)
            
    return sorted(lines, key=lambda l: min(w.y for w in l.words))

def _extract_field(lines: List[TextLine], regex_patterns: List[str], field_name: str) -> ExtractedField:
    candidates = []
    for pattern in regex_patterns:
        for line in lines:
            match = re.search(pattern, line.text)
            if match:
                raw_value = match.group(1).strip()
                candidates.append(ExtractedField(
                    status=FieldStatus.OK,
                    raw_value=raw_value,
                    parsed_value=raw_value,
                    region=line.region
                ))
    
    if not candidates:
        return ExtractedField(
            status=FieldStatus.MISSING,
            reason=f"No regex patterns matched for {field_name}"
        )
        
    if len(candidates) == 1:
        return candidates[0]
        
    # Multiple candidates found, check if they are identical
    # Sometimes the same line matches multiple patterns or overlapping patterns
    unique_raw_values = {c.raw_value for c in candidates}
    if len(unique_raw_values) == 1:
        return candidates[0]
        
    return ExtractedField(
        status=FieldStatus.AMBIGUOUS,
        reason=f"Multiple plausible candidates found for {field_name}",
        candidates=candidates
    )

def _missing_field(field_name: str) -> ExtractedField:
    return ExtractedField(status=FieldStatus.MISSING, reason=f"Not implemented / Not found: {field_name}")

PATTERNS = {
    "invoice_number": [r"(?i)\binvoice\s*(?:no|number|#)[\s:]*([A-Z0-9\-]+)"],
    "invoice_date": [r"(?i)\b(?:invoice\s*)?date[\s:]*([\d\-\/A-Za-z]+)"],
    "vendor_name": [r"(?i)\bvendor[\s:]*([A-Za-z0-9\s]+)"],
    "customer_name": [r"(?i)\b(?:customer|bill to)[\s:]*([A-Za-z0-9\s]+)"],
    "vehicle_number": [r"(?i)\bvehicle\s*(?:no|number|#)[\s:]*([A-Z0-9\-]+)"],
    "claim_number": [r"(?i)\bclaim\s*(?:no|number|#)[\s:]*([A-Z0-9\-]+)"],
    "policy_number": [r"(?i)\bpolicy\s*(?:no|number|#)[\s:]*([A-Z0-9\-]+)"],
    "vin_chassis_number": [r"(?i)\b(?:vin|chassis)\s*(?:no|number|#)?[\s:]*([A-Z0-9\-]+)"],
    "subtotal": [r"(?i)\bsubtotal\b.*?([\$€£₹\u20b9]*\s*[0-9\,\.]{3,})"],
    "taxes": [r"(?i)\b(?:tax(?:es)?|gst|vat)\b.*?([\$€£₹\u20b9]*\s*[0-9\,\.]{3,})"],
    "discounts": [r"(?i)\bdiscount(?:s)?\b.*?([\$€£₹\u20b9]*\s*[0-9\,\.]{3,})"],
    "additional_charges": [r"(?i)\b(?:additional|other)\s*charges\b.*?([\$€£₹\u20b9]*\s*[0-9\,\.]{3,})"],
    "grand_total": [r"(?i)\b(?:grand\s*total|total|amount\s*due|amount)\b.*?([\$€£₹\u20b9]*\s*[0-9\,\.]{3,})"]
}

# Fix invoice_date pattern manually since it was above the replacement block:
PATTERNS["invoice_date"] = [r"(?i)(?<!due\s)\b(?:invoice\s*)?date[\s:]*([\d\-\/A-Za-z]+)"]

def extract_invoice_pack(ocr_result: OCRResult) -> ExtractedInvoicePack:
    all_lines: List[TextLine] = []
    for page in ocr_result.pages:
        all_lines.extend(_group_words_into_lines(page))
        
    return ExtractedInvoicePack(
        invoice_number=_extract_field(all_lines, PATTERNS["invoice_number"], "invoice_number"),
        invoice_date=_extract_field(all_lines, PATTERNS["invoice_date"], "invoice_date"),
        vendor_name=_extract_field(all_lines, PATTERNS["vendor_name"], "vendor_name"),
        customer_name=_extract_field(all_lines, PATTERNS["customer_name"], "customer_name"),
        vehicle_number=_extract_field(all_lines, PATTERNS["vehicle_number"], "vehicle_number"),
        claim_number=_extract_field(all_lines, PATTERNS["claim_number"], "claim_number"),
        policy_number=_extract_field(all_lines, PATTERNS["policy_number"], "policy_number"),
        vin_chassis_number=_extract_field(all_lines, PATTERNS["vin_chassis_number"], "vin_chassis_number"),
        subtotal=_extract_field(all_lines, PATTERNS["subtotal"], "subtotal"),
        taxes=_extract_field(all_lines, PATTERNS["taxes"], "taxes"),
        discounts=_extract_field(all_lines, PATTERNS["discounts"], "discounts"),
        additional_charges=_extract_field(all_lines, PATTERNS["additional_charges"], "additional_charges"),
        grand_total=_extract_field(all_lines, PATTERNS["grand_total"], "grand_total"),
        line_items=_extract_line_items(all_lines)
    )

def _extract_line_items(lines: List[TextLine]) -> List[ExtractedLineItem]:
    line_items = []
    # Simple regex: Description (greedy string), Qty (digits), Price (currency), Amount (currency)
    # Looks for lines with at least a description and an amount at the end
    # Using a simplified heuristic for demo purposes.
    pattern = r"(.+?)\s+(\d+)\s+([\$€£₹\u20b9]?\s*[0-9\,\.]+)\s+([\$€£₹\u20b9]?\s*[0-9\,\.]+)$"
    for line in lines:
        match = re.search(pattern, line.text)
        if match:
            desc, qty, price, amt = match.groups()
            line_items.append(ExtractedLineItem(
                description=ExtractedField(status=FieldStatus.OK, raw_value=desc.strip(), parsed_value=desc.strip(), region=line.region),
                quantity=ExtractedField(status=FieldStatus.OK, raw_value=qty.strip(), parsed_value=qty.strip(), region=line.region),
                unit_price=ExtractedField(status=FieldStatus.OK, raw_value=price.strip(), parsed_value=price.strip(), region=line.region),
                amount=ExtractedField(status=FieldStatus.OK, raw_value=amt.strip(), parsed_value=amt.strip(), region=line.region)
            ))
    return line_items
