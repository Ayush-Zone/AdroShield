"""Structured document representations for Phase 4."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Detected conceptual type of the document."""
    INVOICE = "invoice"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class Region(BaseModel):
    """Normalized spatial region bounding a piece of text on a page."""
    page_number: int = Field(..., ge=1, description="1-based page number")
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., ge=0.0, le=1.0)
    height: float = Field(..., ge=0.0, le=1.0)


class FieldEvidence(BaseModel):
    """Raw extracted field value alongside its spatial evidence."""
    raw_value: str = Field(..., description="The raw string extracted by OCR")
    region: Optional[Region] = Field(default=None, description="Spatial location where this value was found")


class InvoiceLineItem(BaseModel):
    """Structured line item extracted from an invoice."""
    description: Optional[FieldEvidence] = None
    quantity: Optional[FieldEvidence] = None
    unit_price: Optional[FieldEvidence] = None
    amount: Optional[FieldEvidence] = None


class StructuredInvoice(BaseModel):
    """Structured representation of an invoice or repair bill.
    
    All fields preserve raw string values. Normalization is reserved for Phase 5.
    Missing fields remain None.
    """
    document_id: str = Field(..., min_length=1)
    document_type: DocumentType = Field(default=DocumentType.UNKNOWN)
    
    # Basic Fields
    invoice_number: Optional[FieldEvidence] = None
    invoice_date: Optional[FieldEvidence] = None
    vendor_name: Optional[FieldEvidence] = None
    customer_name: Optional[FieldEvidence] = None
    
    # Claim / Vehicle Fields
    vehicle_number: Optional[FieldEvidence] = None
    registration_number: Optional[FieldEvidence] = None
    claim_number: Optional[FieldEvidence] = None
    policy_number: Optional[FieldEvidence] = None
    vin_chassis_number: Optional[FieldEvidence] = None
    
    # Financial Fields
    subtotal: Optional[FieldEvidence] = None
    taxes: Optional[FieldEvidence] = None
    discounts: Optional[FieldEvidence] = None
    additional_charges: Optional[FieldEvidence] = None
    grand_total: Optional[FieldEvidence] = None
    
    # Line Items
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
