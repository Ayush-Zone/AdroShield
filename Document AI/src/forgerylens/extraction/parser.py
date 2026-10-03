"""Parser for converting OCR observations into structured documents."""

import re
from typing import List, Optional

from forgerylens.contracts.ocr import OCRResult, OCRWord, OCRPage
from forgerylens.contracts.spatial import normalize_bbox
from forgerylens.contracts.structured import (
    DocumentType,
    FieldEvidence,
    InvoiceLineItem,
    Region,
    StructuredInvoice
)
from forgerylens.extraction import patterns

class TextLine:
    """Helper class representing a horizontal line of text."""
    def __init__(self, page_num: int):
        self.page_number = page_num
        self.words: List[OCRWord] = []
        
    def add_word(self, word: OCRWord):
        self.words.append(word)
        # Sort words by x coordinate
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
        
        # Ensure bounding boxes are canonically mapped
        nx, ny, nw, nh = normalize_bbox(x_min, y_min, x_max - x_min, y_max - y_min, 1.0, 1.0)
        
        return Region(
            page_number=self.page_number,
            x=nx,
            y=ny,
            width=nw,
            height=nh
        )

def _group_words_into_lines(page: OCRPage, y_tolerance: float = 0.015) -> List[TextLine]:
    """Group words into horizontal text lines."""
    lines: List[TextLine] = []
    # Sort words primarily by y, then by x
    sorted_words = sorted(page.words, key=lambda w: (w.y, w.x))
    
    for word in sorted_words:
        matched_line = None
        for line in lines:
            # If word vertically overlaps with the line
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
            
    # Return lines sorted by y position
    return sorted(lines, key=lambda l: min(w.y for w in l.words))

def _detect_document_type(full_text: str) -> DocumentType:
    """Detect if the document is an invoice using simple heuristics."""
    text_lower = full_text.lower()
    for indicator in patterns.INVOICE_INDICATORS:
        if re.search(indicator, text_lower):
            return DocumentType.INVOICE
    return DocumentType.UNKNOWN

def _extract_field(lines: List[TextLine], regex_patterns: List[str]) -> Optional[FieldEvidence]:
    """Extract a field using a list of regex patterns against all text lines.
    
    Patterns are ordered by specificity (strongest first).
    """
    for pattern in regex_patterns:
        for line in lines:
            match = re.search(pattern, line.text)
            if match:
                raw_value = match.group(1).strip()
                return FieldEvidence(
                    raw_value=raw_value,
                    region=line.region
                )
    return None

def _extract_line_items(lines: List[TextLine]) -> List[InvoiceLineItem]:
    """Very basic heuristic for extracting line items.
    
    This looks for rows that have characteristic line item layouts
    (e.g., Description + Number + Number).
    """
    line_items = []
    in_table = False
    
    # We look for a header row to start parsing
    for i, line in enumerate(lines):
        line_text_lower = line.text.lower()
        
        # Detect table start
        if not in_table:
            has_desc = "description" in line_text_lower or "particulars" in line_text_lower or "item" in line_text_lower
            has_qty_rate = "qty" in line_text_lower or "quantity" in line_text_lower or "rate" in line_text_lower or "price" in line_text_lower
            if has_desc and has_qty_rate:
                in_table = True
            continue
            
        # Stop table parsing if we hit totals
        if any(keyword in line_text_lower for keyword in ["subtotal", "sub-total", "tax", "grand total", "total amount"]):
            break
            
        # Inside table, attempt to parse item
        # Typical format: [Description words...] [Qty] [Rate] [Amount]
        words = line.text.split()
        if len(words) >= 4:
            # Check if last three elements are numeric-ish
            # Simple check: do they contain numbers
            if any(c.isdigit() for c in words[-1]) and any(c.isdigit() for c in words[-2]):
                qty_str = words[-3]
                rate_str = words[-2]
                amount_str = words[-1]
                desc_str = " ".join(words[:-3])
                
                # Basic sanity check that qty/rate/amount aren't just text
                if any(c.isdigit() for c in qty_str) or qty_str.lower() == "na":
                    item = InvoiceLineItem(
                        description=FieldEvidence(raw_value=desc_str, region=line.region),
                        quantity=FieldEvidence(raw_value=qty_str, region=line.region),
                        unit_price=FieldEvidence(raw_value=rate_str, region=line.region),
                        amount=FieldEvidence(raw_value=amount_str, region=line.region)
                    )
                    line_items.append(item)
                    
    return line_items

def parse_document(ocr_result: OCRResult) -> StructuredInvoice:
    """Parse an OCRResult into a StructuredInvoice."""
    # Gather all text and lines across pages
    full_text = ""
    all_lines: List[TextLine] = []
    
    for page in ocr_result.pages:
        full_text += page.full_text + "\\n"
        page_lines = _group_words_into_lines(page)
        all_lines.extend(page_lines)
        
    doc_type = _detect_document_type(full_text)
    
    invoice = StructuredInvoice(
        document_id=ocr_result.document_id,
        document_type=doc_type
    )
    
    if doc_type == DocumentType.INVOICE:
        # Extract basic fields
        invoice.invoice_number = _extract_field(all_lines, patterns.INVOICE_NUMBER_PATTERNS)
        invoice.invoice_date = _extract_field(all_lines, patterns.INVOICE_DATE_PATTERNS)
        invoice.vendor_name = _extract_field(all_lines, patterns.VENDOR_PATTERNS)
        invoice.customer_name = _extract_field(all_lines, patterns.CUSTOMER_PATTERNS)
        
        # Vehicle / claim fields
        invoice.vehicle_number = _extract_field(all_lines, patterns.VEHICLE_NUMBER_PATTERNS)
        invoice.claim_number = _extract_field(all_lines, patterns.CLAIM_NUMBER_PATTERNS)
        invoice.policy_number = _extract_field(all_lines, patterns.POLICY_NUMBER_PATTERNS)
        invoice.vin_chassis_number = _extract_field(all_lines, patterns.VIN_PATTERNS)
        
        # Financial fields
        invoice.subtotal = _extract_field(all_lines, patterns.SUBTOTAL_PATTERNS)
        invoice.taxes = _extract_field(all_lines, patterns.TAX_PATTERNS)
        invoice.discounts = _extract_field(all_lines, patterns.DISCOUNT_PATTERNS)
        invoice.additional_charges = _extract_field(all_lines, patterns.ADDITIONAL_CHARGES_PATTERNS)
        invoice.grand_total = _extract_field(all_lines, patterns.GRAND_TOTAL_PATTERNS)
        
        # Line items
        invoice.line_items = _extract_line_items(all_lines)
        
    return invoice
