"""Image document ingestion and validation module."""

import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image, UnidentifiedImageError

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import IngestedDocument, PageInfo

logger = logging.getLogger(__name__)


def inspect_image(
    file_path: Path,
    evidence_id: str,
    file_size_bytes: int,
    doc_format: DocumentFormat,
    mime_type: str,
    initial_warnings: Optional[List[str]] = None,
) -> IngestedDocument:
    """Inspect and validate an image document (PNG, JPG, JPEG).

    Decodes image metadata, checks integrity, and captures dimensions
    without performing OCR or image tampering analysis.
    """
    warnings: List[str] = list(initial_warnings or [])
    filename = file_path.name

    # 1. Verification pass to check for file corruption / truncation
    try:
        with Image.open(file_path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        return IngestedDocument(
            document_id=evidence_id,
            source_path=str(file_path.resolve()),
            filename=filename,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            format=doc_format,
            page_count=0,
            pages=[],
            status=IngestionStatus.CORRUPT,
            warnings=warnings,
            errors=[f"corrupt image: cannot decode image data: {str(e)}"],
        )

    # 2. Re-open to extract dimensions and DPI metadata (verify closes/invalidates the image stream)
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                return IngestedDocument(
                    document_id=evidence_id,
                    source_path=str(file_path.resolve()),
                    filename=filename,
                    file_size_bytes=file_size_bytes,
                    mime_type=mime_type,
                    format=doc_format,
                    page_count=0,
                    pages=[],
                    status=IngestionStatus.CORRUPT,
                    warnings=warnings,
                    errors=["invalid image dimensions: width or height is zero or negative"],
                )

            dpi_val: Optional[int] = None
            raw_dpi = img.info.get("dpi")
            if raw_dpi and isinstance(raw_dpi, (tuple, list)) and len(raw_dpi) > 0:
                try:
                    dpi_val = int(round(raw_dpi[0]))
                except (ValueError, TypeError):
                    dpi_val = None

            page = PageInfo(
                page_number=1,
                width=float(width),
                height=float(height),
                dpi=dpi_val,
                is_readable=True,
            )

            return IngestedDocument(
                document_id=evidence_id,
                source_path=str(file_path.resolve()),
                filename=filename,
                file_size_bytes=file_size_bytes,
                mime_type=mime_type,
                format=doc_format,
                page_count=1,
                pages=[page],
                status=IngestionStatus.VALID,
                warnings=warnings,
                errors=[],
            )

    except Exception as e:
        return IngestedDocument(
            document_id=evidence_id,
            source_path=str(file_path.resolve()),
            filename=filename,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            format=doc_format,
            page_count=0,
            pages=[],
            status=IngestionStatus.CORRUPT,
            warnings=warnings,
            errors=[f"unreadable image: failed reading image attributes: {str(e)}"],
        )
