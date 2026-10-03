from enum import Enum
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

from forgerylens.contracts.structured import DocumentType, Region, FieldEvidence

T = TypeVar("T")

class NormalizationStatus(str, Enum):
    """Outcomes of the normalization process."""
    SUCCESS = "success"
    UNCHANGED = "unchanged"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


class NormalizedField(BaseModel, Generic[T]):
    """A field that has been passed through the normalization layer.
    
    Preserves provenance (raw_value, region) while attempting to provide
    a standardized representation (normalized_value).
    """
    raw_value: str = Field(..., description="The original extracted string")
    region: Optional[Region] = Field(default=None, description="Spatial location where this value was found")
    normalized_value: Optional[T] = Field(default=None, description="The canonical representation, if safe to infer")
    status: NormalizationStatus = Field(default=NormalizationStatus.UNCHANGED)
    warnings: List[str] = Field(default_factory=list, description="Any issues encountered during normalization")

    @classmethod
    def from_evidence(cls, evidence: FieldEvidence, normalized_value: Optional[T] = None, status: NormalizationStatus = NormalizationStatus.UNCHANGED, warnings: Optional[List[str]] = None) -> "NormalizedField[T]":
        """Helper to create from Phase 4 evidence."""
        return cls(
            raw_value=evidence.raw_value,
            region=evidence.region,
            normalized_value=normalized_value,
            status=status,
            warnings=warnings or []
        )


class CurrencyAmount(BaseModel):
    """Normalized currency amount."""
    amount: float = Field(..., description="The parsed decimal amount")
    currency: Optional[str] = Field(default=None, description="The identified currency code (e.g., INR)")


class NormalizedLineItem(BaseModel):
    """Normalized representation of a line item."""
    description: Optional[NormalizedField[str]] = None
    quantity: Optional[NormalizedField[float]] = None
    unit_price: Optional[NormalizedField[CurrencyAmount]] = None
    amount: Optional[NormalizedField[CurrencyAmount]] = None


class NormalizedInvoice(BaseModel):
    """Canonical representation of an invoice after Phase 5 normalization."""
    document_id: str = Field(..., min_length=1)
    document_type: DocumentType = Field(default=DocumentType.UNKNOWN)
    
    # Basic Fields
    invoice_number: Optional[NormalizedField[str]] = None
    invoice_date: Optional[NormalizedField[str]] = None  # Stored as ISO format string YYYY-MM-DD
    vendor_name: Optional[NormalizedField[str]] = None
    customer_name: Optional[NormalizedField[str]] = None
    
    # Claim / Vehicle Fields
    vehicle_number: Optional[NormalizedField[str]] = None
    registration_number: Optional[NormalizedField[str]] = None
    claim_number: Optional[NormalizedField[str]] = None
    policy_number: Optional[NormalizedField[str]] = None
    vin_chassis_number: Optional[NormalizedField[str]] = None
    
    # Financial Fields
    subtotal: Optional[NormalizedField[CurrencyAmount]] = None
    taxes: Optional[NormalizedField[CurrencyAmount]] = None
    discounts: Optional[NormalizedField[CurrencyAmount]] = None
    additional_charges: Optional[NormalizedField[CurrencyAmount]] = None
    grand_total: Optional[NormalizedField[CurrencyAmount]] = None
    
    # Line Items
    line_items: List[NormalizedLineItem] = Field(default_factory=list)
