"""Regex patterns and heuristics for structured field extraction."""

# Invoice type indicators
INVOICE_INDICATORS = [
    r"invoice",
    r"bill",
    r"receipt",
    r"tax invoice",
    r"estimate",
    r"quotation",
    r"repair order"
]

# Basic Fields
INVOICE_NUMBER_PATTERNS = [
    r"(?i)invoice\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)",
    r"(?i)bill\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)",
    r"(?i)receipt\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)"
]

INVOICE_DATE_PATTERNS = [
    r"(?i)invoice\s*date\s*[:\-\s]\s*([a-zA-Z0-9\/\-\.]+)",
    r"(?i)\bdate\s*[:\-\s]\s*([0-9]{2,4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,4})",
    r"(?i)\bdate\s*[:\-\s]\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
    r"(?i)\bdate\s*[:\-\s]\s*([a-zA-Z]{3,}\s+[0-9]{1,2},?\s+[0-9]{4})"
]

VENDOR_PATTERNS = [
    r"(?i)(?:vendor|dealer|service center|issued by)\s*[:\-\s]\s*([a-zA-Z0-9\s\,\.]+)"
]

CUSTOMER_PATTERNS = [
    r"(?i)(?:customer|billed to|client|name)\s*[:\-\s]\s*([a-zA-Z0-9\s\,\.]+)"
]

# Vehicle / Claim Fields
VEHICLE_NUMBER_PATTERNS = [
    r"(?i)(?:vehicle|veh)\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)",
    r"(?i)\breg\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)"
]

CLAIM_NUMBER_PATTERNS = [
    r"(?i)\bclaim\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)"
]

POLICY_NUMBER_PATTERNS = [
    r"(?i)\bpolicy\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9\-]+)"
]

VIN_PATTERNS = [
    r"(?i)(?:vin|chassis)\s*(?:no|number|#)?\s*[:\-\s]\s*([a-zA-Z0-9]{11,17})"
]

# Financial Fields
SUBTOTAL_PATTERNS = [
    r"(?i)\bsub[\-\s]?total\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)"
]

TAX_PATTERNS = [
    r"(?i)\b(?:tax|cgst|sgst|igst|vat|gst)\b\s*[\(0-9%\)]*\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)"
]

DISCOUNT_PATTERNS = [
    r"(?i)\bdiscount\b\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)"
]

ADDITIONAL_CHARGES_PATTERNS = [
    r"(?i)\b(?:freight|shipping|handling|additional)\b\s*(?:charges)?\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)"
]

GRAND_TOTAL_PATTERNS = [
    r"(?i)\b(?:grand|net|final)\b\s*(?:amount|total)?\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)",
    r"(?i)\btotal\b\s*(?:amount)?\s*[:\-\s]?\s*(?:Rs\.?|INR|₹|\$)?\s*([0-9\,\.\s]+)"
]

# Line items header keywords
LINE_ITEM_HEADERS = [
    r"(?i)description",
    r"(?i)particulars",
    r"(?i)item",
    r"(?i)qty",
    r"(?i)quantity",
    r"(?i)rate",
    r"(?i)price",
    r"(?i)amount",
    r"(?i)total"
]
