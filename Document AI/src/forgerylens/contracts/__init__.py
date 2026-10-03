"""Contracts package for ForgeryLens."""

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import PageInfo, IngestedDocument
from forgerylens.contracts.ocr import OCRExtractionMethod, OCRWord, OCRPage, OCRResult
from forgerylens.contracts.structured import (
    DocumentType,
    Region,
    FieldEvidence,
    InvoiceLineItem,
    StructuredInvoice,
)
from forgerylens.contracts.normalized import (
    NormalizationStatus,
    NormalizedField,
    CurrencyAmount,
    NormalizedLineItem,
    NormalizedInvoice,
)
from forgerylens.contracts.validation import (
    ValidationStatus,
    ValidationSeverity,
    ValidationFinding,
    ValidationResult,
)

__all__ = [
    "DocumentFormat",
    "IngestionStatus",
    "PageInfo",
    "IngestedDocument",
    "OCRExtractionMethod",
    "OCRWord",
    "OCRPage",
    "OCRResult",
    "DocumentType",
    "Region",
    "FieldEvidence",
    "InvoiceLineItem",
    "StructuredInvoice",
    "NormalizationStatus",
    "NormalizedField",
    "CurrencyAmount",
    "NormalizedLineItem",
    "NormalizedInvoice",
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationFinding",
    "ValidationResult",
]
