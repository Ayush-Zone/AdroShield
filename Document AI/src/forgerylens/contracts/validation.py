"""Validation contracts for ForgeryLens Phase 6."""

from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """The outcome of a specific validation rule."""
    VALID = "valid"
    INVALID = "invalid"  # Discrepancy found
    MISSING = "missing"  # Required field is missing
    UNABLE_TO_VERIFY = "unable_to_verify"  # Ambiguous or insufficient information


class ValidationSeverity(str, Enum):
    """The severity of a finding."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ValidationFinding(BaseModel):
    """A single finding resulting from a validation rule."""
    rule_name: str = Field(..., description="Name of the validation rule (e.g., 'line_item_arithmetic')")
    status: ValidationStatus = Field(..., description="Outcome of the validation")
    severity: ValidationSeverity = Field(..., description="Severity of the finding")
    message: str = Field(..., description="Human-readable explanation of the finding")
    
    expected: Optional[str] = Field(default=None, description="Expected value (e.g., '1000.00')")
    observed: Optional[str] = Field(default=None, description="Observed value (e.g., '1200.00')")
    difference: Optional[str] = Field(default=None, description="Mathematical difference if applicable")
    
    # We store involved fields as a generic dict to preserve their state/provenance 
    # without creating recursive or overly complex pydantic links.
    involved_fields: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Key-value mapping of field names to their normalized field representation/provenance"
    )


class ValidationResult(BaseModel):
    """The complete set of validation findings for a document."""
    document_id: str = Field(..., min_length=1)
    findings: List[ValidationFinding] = Field(default_factory=list, description="All validation findings")

    @property
    def has_critical_discrepancies(self) -> bool:
        """Helper to quickly check if any finding is INVALID and CRITICAL."""
        return any(f.status == ValidationStatus.INVALID and f.severity == ValidationSeverity.CRITICAL for f in self.findings)
