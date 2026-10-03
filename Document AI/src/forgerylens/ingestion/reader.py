"""Ingestion reader and orchestrator for ForgeryLens."""

import uuid
from pathlib import Path
from typing import Optional, Union

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import IngestedDocument
from forgerylens.ingestion.validator import validate_file_sanity, DEFAULT_MAX_FILE_SIZE_BYTES
from forgerylens.ingestion.mime import detect_document_format
from forgerylens.ingestion.pdf import inspect_pdf
from forgerylens.ingestion.image import inspect_image


def ingest_document(
    file_path: Union[str, Path],
    evidence_id: Optional[str] = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> IngestedDocument:
    """Ingest and validate an untrusted document file.

    Establishes the boundary between raw uploaded file and downstream
    pipeline stages (OCR, extraction, consistency checks).

    Args:
        file_path: Path to the target document file.
        evidence_id: Optional unique identifier for the evidence. If omitted,
            a UUID will be generated.
        max_file_size_bytes: Maximum allowed file size in bytes (default: 50MB).

    Returns:
        An IngestedDocument representation containing validation status,
        page count, dimensions, and any errors or warnings.
    """
    path_obj = Path(file_path)
    ev_id = evidence_id or str(uuid.uuid4())
    filename = path_obj.name

    # 1. Preliminary filesystem and sanity checks
    is_valid_sanity, header_bytes, file_size, sanity_status, sanity_error = (
        validate_file_sanity(path_obj, max_file_size_bytes=max_file_size_bytes)
    )

    if not is_valid_sanity:
        return IngestedDocument(
            document_id=ev_id,
            source_path=str(path_obj),
            filename=filename,
            file_size_bytes=file_size,
            mime_type="application/octet-stream",
            format=DocumentFormat.UNKNOWN,
            page_count=0,
            pages=[],
            status=sanity_status or IngestionStatus.UNREADABLE,
            warnings=[],
            errors=[sanity_error or "file sanity validation failed"],
        )

    # 2. Format and MIME detection from magic bytes
    doc_format, mime_type, mime_error, warnings = detect_document_format(
        path_obj, header_bytes or b""
    )

    if mime_error or doc_format == DocumentFormat.UNKNOWN:
        # Determine whether this is an unsupported type or a spoofed/corrupted file
        status = (
            IngestionStatus.UNSUPPORTED
            if "unsupported" in (mime_error or "")
            else IngestionStatus.CORRUPT
        )
        return IngestedDocument(
            document_id=ev_id,
            source_path=str(path_obj.resolve()),
            filename=filename,
            file_size_bytes=file_size,
            mime_type=mime_type or "application/octet-stream",
            format=DocumentFormat.UNKNOWN,
            page_count=0,
            pages=[],
            status=status,
            warnings=warnings,
            errors=[mime_error or "unrecognized document format"],
        )

    # 3. Format-specific deep inspection
    if doc_format == DocumentFormat.PDF:
        return inspect_pdf(
            path_obj,
            evidence_id=ev_id,
            file_size_bytes=file_size,
            initial_warnings=warnings,
        )
    elif doc_format in (DocumentFormat.PNG, DocumentFormat.JPEG):
        return inspect_image(
            path_obj,
            evidence_id=ev_id,
            file_size_bytes=file_size,
            doc_format=doc_format,
            mime_type=mime_type,
            initial_warnings=warnings,
        )

    # Fallback for unexpected format state
    return IngestedDocument(
        document_id=ev_id,
        source_path=str(path_obj.resolve()),
        filename=filename,
        file_size_bytes=file_size,
        mime_type=mime_type or "application/octet-stream",
        format=DocumentFormat.UNKNOWN,
        page_count=0,
        pages=[],
        status=IngestionStatus.UNSUPPORTED,
        warnings=warnings,
        errors=[f"unsupported document format: {doc_format}"],
    )
