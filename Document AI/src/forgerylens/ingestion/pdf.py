"""PDF ingestion and validation module."""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import IngestedDocument, PageInfo

logger = logging.getLogger(__name__)

# Standard fallback dimensions (US Letter in points: 8.5 x 11 inches @ 72 dpi)
DEFAULT_PDF_WIDTH_PT = 612.0
DEFAULT_PDF_HEIGHT_PT = 792.0


def _parse_pdf_pure_python(
    file_bytes: bytes,
) -> Tuple[bool, List[PageInfo], List[str], Optional[str]]:
    """Safe pure-Python parser for PDF structure, page count, and dimensions.

    Returns:
        (is_success, pages, warnings, error_message)
    """
    warnings: List[str] = []

    # 1. Header validation
    if not file_bytes.startswith(b"%PDF-"):
        return False, [], warnings, "corrupt PDF: missing %PDF- header signature"

    # 2. EOF marker sanity check
    trailer_window = file_bytes[-1024:] if len(file_bytes) > 1024 else file_bytes
    if b"%%EOF" not in trailer_window:
        warnings.append("PDF trailer marker %%EOF is missing or displaced")

    # 3. Encryption check
    if b"/Encrypt" in file_bytes:
        warnings.append("document contains /Encrypt dictionary; content may be password-protected")

    # 4. Extract page count from /Pages catalog
    count_matches = re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", file_bytes)
    if not count_matches:
        count_matches = re.findall(rb"/Count\s+(\d+)\b[^>]*?/Type\s*/Pages\b", file_bytes)
    if not count_matches:
        count_matches = re.findall(rb"/Count\s+(\d+)", file_bytes)

    page_count: Optional[int] = None
    if count_matches:
        try:
            # Usually the highest count belongs to the root Pages node
            counts = [int(m) for m in count_matches]
            page_count = max(counts)
        except ValueError:
            page_count = None

    # 5. Extract MediaBox dimensions for each page
    mediabox_pattern = re.compile(
        rb"/MediaBox\s*\[\s*([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s*\]"
    )
    mediaboxes: List[Tuple[float, float]] = []
    for match in mediabox_pattern.finditer(file_bytes):
        try:
            x0 = float(match.group(1))
            y0 = float(match.group(2))
            x1 = float(match.group(3))
            y1 = float(match.group(4))
            w = abs(x1 - x0)
            h = abs(y1 - y0)
            if w > 0 and h > 0:
                mediaboxes.append((w, h))
        except (ValueError, IndexError):
            continue

    # 6. Fallback page counting if /Count was absent or invalid
    if page_count is None or page_count <= 0:
        # Count individual /Type /Page objects
        page_obj_matches = re.findall(rb"/Type\s*/Page\b", file_bytes)
        if page_obj_matches:
            page_count = len(page_obj_matches)
        elif mediaboxes:
            page_count = len(mediaboxes)
        else:
            return (
                False,
                [],
                warnings,
                "corrupt PDF: unable to locate valid page catalog or page tree",
            )

    if page_count == 0:
        return False, [], warnings, "unreadable PDF: document contains 0 pages"

    # 7. Construct PageInfo list
    pages: List[PageInfo] = []
    for page_idx in range(1, page_count + 1):
        if page_idx - 1 < len(mediaboxes):
            pw, ph = mediaboxes[page_idx - 1]
        elif mediaboxes:
            # Re-use last known MediaBox (common for multi-page documents sharing same size)
            pw, ph = mediaboxes[-1]
        else:
            pw, ph = DEFAULT_PDF_WIDTH_PT, DEFAULT_PDF_HEIGHT_PT

        pages.append(
            PageInfo(
                page_number=page_idx,
                width=pw,
                height=ph,
                dpi=72,  # standard PDF point resolution
                is_readable=True,
            )
        )

    return True, pages, warnings, None


def inspect_pdf(
    file_path: Path,
    evidence_id: str,
    file_size_bytes: int,
    initial_warnings: Optional[List[str]] = None,
) -> IngestedDocument:
    """Inspect and validate a PDF document.

    Verifies document structure, checks page readability, and captures
    page count and dimensions without performing OCR.
    """
    warnings: List[str] = list(initial_warnings or [])
    filename = file_path.name

    # Try PyMuPDF if installed in the environment
    try:
        import fitz  # PyMuPDF

        try:
            doc = fitz.open(file_path)
            page_count = doc.page_count
            if page_count == 0:
                doc.close()
                return IngestedDocument(
                    document_id=evidence_id,
                    source_path=str(file_path.resolve()),
                    filename=filename,
                    file_size_bytes=file_size_bytes,
                    mime_type="application/pdf",
                    format=DocumentFormat.PDF,
                    page_count=0,
                    pages=[],
                    status=IngestionStatus.CORRUPT,
                    warnings=warnings,
                    errors=["unreadable PDF: document contains 0 pages"],
                )

            pages: List[PageInfo] = []
            for i in range(page_count):
                page = doc[i]
                rect = page.rect
                pages.append(
                    PageInfo(
                        page_number=i + 1,
                        width=float(rect.width),
                        height=float(rect.height),
                        dpi=72,
                        is_readable=True,
                    )
                )
            doc.close()

            return IngestedDocument(
                document_id=evidence_id,
                source_path=str(file_path.resolve()),
                filename=filename,
                file_size_bytes=file_size_bytes,
                mime_type="application/pdf",
                format=DocumentFormat.PDF,
                page_count=page_count,
                pages=pages,
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
                mime_type="application/pdf",
                format=DocumentFormat.PDF,
                page_count=0,
                pages=[],
                status=IngestionStatus.CORRUPT,
                warnings=warnings,
                errors=[f"corrupt PDF: {str(e)}"],
            )
    except ImportError:
        # PyMuPDF not available; use pure-Python parser
        pass

    # Pure Python inspection
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        return IngestedDocument(
            document_id=evidence_id,
            source_path=str(file_path.resolve()),
            filename=filename,
            file_size_bytes=file_size_bytes,
            mime_type="application/pdf",
            format=DocumentFormat.PDF,
            page_count=0,
            pages=[],
            status=IngestionStatus.UNREADABLE,
            warnings=warnings,
            errors=[f"document could not be opened: {str(e)}"],
        )

    success, pages, parse_warnings, parse_error = _parse_pdf_pure_python(pdf_bytes)
    warnings.extend(parse_warnings)

    if not success or parse_error:
        return IngestedDocument(
            document_id=evidence_id,
            source_path=str(file_path.resolve()),
            filename=filename,
            file_size_bytes=file_size_bytes,
            mime_type="application/pdf",
            format=DocumentFormat.PDF,
            page_count=0,
            pages=[],
            status=IngestionStatus.CORRUPT,
            warnings=warnings,
            errors=[parse_error or "corrupt PDF: structure validation failed"],
        )

    return IngestedDocument(
        document_id=evidence_id,
        source_path=str(file_path.resolve()),
        filename=filename,
        file_size_bytes=file_size_bytes,
        mime_type="application/pdf",
        format=DocumentFormat.PDF,
        page_count=len(pages),
        pages=pages,
        status=IngestionStatus.VALID,
        warnings=warnings,
        errors=[],
    )
