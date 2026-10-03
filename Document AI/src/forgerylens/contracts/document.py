"""Document representations for ingestion and validation."""

from typing import List, Optional
from pydantic import BaseModel, Field

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus


class PageInfo(BaseModel):
    """Metadata describing an individual page within an ingested document."""

    page_number: int = Field(..., ge=1, description="1-based page number.")
    width: float = Field(..., gt=0, description="Page width in points (PDF) or pixels (image).")
    height: float = Field(..., gt=0, description="Page height in points (PDF) or pixels (image).")
    dpi: Optional[int] = Field(default=None, gt=0, description="DPI resolution if available.")
    is_readable: bool = Field(default=True, description="Whether the page was successfully parsed.")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings for this page.")


class IngestedDocument(BaseModel):
    """Normalized internal representation of an ingested document.

    This represents the validated document boundary between raw file input
    and subsequent pipeline phases (OCR, structured extraction, forensics).
    """

    document_id: str = Field(..., min_length=1, description="Unique identifier for the document or evidence.")
    source_path: str = Field(..., min_length=1, description="Source file path.")
    filename: str = Field(..., min_length=1, description="Basename of the file.")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    mime_type: str = Field(..., min_length=1, description="Detected MIME type.")
    format: DocumentFormat = Field(..., description="Normalized document format.")
    page_count: int = Field(default=0, ge=0, description="Total number of readable pages.")
    pages: List[PageInfo] = Field(default_factory=list, description="Metadata for each page.")
    status: IngestionStatus = Field(..., description="Overall ingestion outcome status.")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings.")
    errors: List[str] = Field(default_factory=list, description="Fatal validation or parsing errors.")

    @property
    def is_valid(self) -> bool:
        """Return True if the document was successfully ingested without fatal errors."""
        return self.status == IngestionStatus.VALID and len(self.errors) == 0
