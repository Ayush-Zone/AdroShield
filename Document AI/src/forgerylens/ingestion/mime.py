"""MIME type and magic byte detection for document ingestion."""

from pathlib import Path
from typing import Tuple, Optional, List

from forgerylens.contracts.enums import DocumentFormat


# Standard magic signatures
PDF_MAGIC = b"%PDF-"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

# Extension mapping
EXTENSION_MAP = {
    ".pdf": (DocumentFormat.PDF, "application/pdf"),
    ".png": (DocumentFormat.PNG, "image/png"),
    ".jpg": (DocumentFormat.JPEG, "image/jpeg"),
    ".jpeg": (DocumentFormat.JPEG, "image/jpeg"),
}


def detect_document_format(
    file_path: Path, header_bytes: bytes
) -> Tuple[DocumentFormat, str, Optional[str], List[str]]:
    """Detect the document format and MIME type using magic bytes and extension.

    Returns:
        (format, mime_type, error_message, warnings)
    """
    warnings: List[str] = []
    ext = file_path.suffix.lower()

    # 1. Inspect magic bytes first (content truth)
    detected_format: Optional[DocumentFormat] = None
    detected_mime: Optional[str] = None

    if header_bytes.startswith(PDF_MAGIC):
        detected_format = DocumentFormat.PDF
        detected_mime = "application/pdf"
    elif header_bytes.startswith(PNG_MAGIC):
        detected_format = DocumentFormat.PNG
        detected_mime = "image/png"
    elif header_bytes.startswith(JPEG_MAGIC):
        detected_format = DocumentFormat.JPEG
        detected_mime = "image/jpeg"

    # 2. Check extension expectations
    expected = EXTENSION_MAP.get(ext)

    if detected_format is None:
        # Magic bytes do not match any supported format
        if expected:
            expected_format, _ = expected
            return (
                DocumentFormat.UNKNOWN,
                "application/octet-stream",
                f"file extension is '{ext}' but file content does not match expected {expected_format.value.upper()} signature",
                warnings,
            )
        return (
            DocumentFormat.UNKNOWN,
            "application/octet-stream",
            f"unsupported document type with extension '{ext or 'none'}'",
            warnings,
        )

    # 3. If magic bytes match, check if extension matches
    if expected:
        expected_format, expected_mime = expected
        if detected_format != expected_format:
            return (
                DocumentFormat.UNKNOWN,
                detected_mime,
                f"file extension mismatch: extension is '{ext}' but content signature is {detected_format.value.upper()}",
                warnings,
            )
    else:
        # File has non-standard extension but valid magic bytes
        warnings.append(
            f"file has non-standard extension '{ext}' for detected format {detected_format.value.upper()}"
        )

    return (detected_format, detected_mime, None, warnings)
