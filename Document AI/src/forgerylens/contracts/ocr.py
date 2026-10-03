"""OCR representations and contracts."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from forgerylens.contracts.enums import IngestionStatus


class OCRExtractionMethod(str, Enum):
    """Method used to extract text from a document page."""
    NATIVE_PDF = "native_pdf"
    TESSERACT_OCR = "tesseract_ocr"


class OCRWord(BaseModel):
    """Represents a single word extracted from a document page."""

    text: str = Field(..., description="The recognized text for the word.")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="OCR engine confidence score (0-100)."
    )
    # Normalized bounding box (0.0 to 1.0)
    x: float = Field(..., ge=0.0, le=1.0, description="Normalized X coordinate of top-left corner.")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized Y coordinate of top-left corner.")
    width: float = Field(..., ge=0.0, le=1.0, description="Normalized width of the bounding box.")
    height: float = Field(..., ge=0.0, le=1.0, description="Normalized height of the bounding box.")


class OCRPage(BaseModel):
    """Represents OCR observations for a single page."""

    page_number: int = Field(..., ge=1, description="1-based page number.")
    extraction_method: OCRExtractionMethod = Field(..., description="Method used to extract text.")
    full_text: str = Field(..., description="Complete text extracted from the page.")
    words: List[OCRWord] = Field(default_factory=list, description="Word-level extraction details.")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal extraction warnings.")


class OCRResult(BaseModel):
    """Represents the complete OCR observation for a document.
    
    This is purely observational evidence and does not evaluate
    document authenticity or claim fraud.
    """

    document_id: str = Field(..., min_length=1, description="Unique identifier matching the ingested document.")
    pages: List[OCRPage] = Field(default_factory=list, description="Extracted text per page.")
    status: IngestionStatus = Field(..., description="Overall extraction outcome status.")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal document-level warnings.")
    errors: List[str] = Field(default_factory=list, description="Fatal extraction errors.")

    @property
    def is_valid(self) -> bool:
        """Return True if the document was successfully processed without fatal errors."""
        return self.status == IngestionStatus.VALID and len(self.errors) == 0
