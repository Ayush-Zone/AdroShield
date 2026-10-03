"""Contracts package for ForgeryLens."""

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import PageInfo, IngestedDocument
from forgerylens.contracts.ocr import OCRExtractionMethod, OCRWord, OCRPage, OCRResult

__all__ = [
    "DocumentFormat",
    "IngestionStatus",
    "PageInfo",
    "IngestedDocument",
    "OCRExtractionMethod",
    "OCRWord",
    "OCRPage",
    "OCRResult",
]
