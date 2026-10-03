from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel
from forgerylens.contracts.structured import Region

class FieldStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"

class ExtractedField(BaseModel):
    """Represents a single extracted field, handling missing and ambiguous states."""
    status: FieldStatus
    raw_value: Optional[str] = None
    parsed_value: Optional[Any] = None
    region: Optional[Region] = None
    reason: Optional[str] = None
    candidates: Optional[List['ExtractedField']] = None

class ExtractedLineItem(BaseModel):
    description: ExtractedField
    quantity: ExtractedField
    unit_price: ExtractedField
    amount: ExtractedField

class ExtractedInvoicePack(BaseModel):
    # Basic
    invoice_number: ExtractedField
    invoice_date: ExtractedField
    vendor_name: ExtractedField
    customer_name: ExtractedField
    
    # Vehicle / Claim
    vehicle_number: ExtractedField
    claim_number: ExtractedField
    policy_number: ExtractedField
    vin_chassis_number: ExtractedField
    
    # Financial
    subtotal: ExtractedField
    taxes: ExtractedField
    discounts: ExtractedField
    additional_charges: ExtractedField
    grand_total: ExtractedField
    
    # Line Items
    line_items: List[ExtractedLineItem]
