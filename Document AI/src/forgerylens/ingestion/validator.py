"""Preliminary filesystem and sanity validation for document ingestion."""

from pathlib import Path
from typing import Optional, Tuple

from forgerylens.contracts.enums import IngestionStatus

# Default maximum document file size: 50 MB
DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
HEADER_READ_BYTES = 1024


def validate_file_sanity(
    file_path: Path, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
) -> Tuple[bool, Optional[bytes], int, Optional[IngestionStatus], Optional[str]]:
    """Perform preliminary filesystem checks on the target document.

    Checks:
        1. File existence
        2. Regular file vs directory
        3. Empty file (0 bytes)
        4. Maximum size limit
        5. Readability & permissions

    Returns:
        (is_valid, header_bytes, file_size, status, error_message)
    """
    if not file_path.exists():
        return (
            False,
            None,
            0,
            IngestionStatus.UNREADABLE,
            f"file not found: {file_path}",
        )

    if not file_path.is_file():
        return (
            False,
            None,
            0,
            IngestionStatus.UNREADABLE,
            f"target path is not a regular file: {file_path}",
        )

    try:
        stat_result = file_path.stat()
        file_size = stat_result.st_size
    except OSError as e:
        return (
            False,
            None,
            0,
            IngestionStatus.UNREADABLE,
            f"unable to access file attributes: {e.strerror or str(e)}",
        )

    if file_size == 0:
        return (
            False,
            None,
            0,
            IngestionStatus.EMPTY,
            f"empty file (0 bytes): {file_path.name}",
        )

    if file_size > max_file_size_bytes:
        return (
            False,
            None,
            file_size,
            IngestionStatus.UNREADABLE,
            f"file exceeds maximum allowed size ({file_size} > {max_file_size_bytes} bytes)",
        )

    try:
        with open(file_path, "rb") as f:
            header_bytes = f.read(HEADER_READ_BYTES)
    except PermissionError:
        return (
            False,
            None,
            file_size,
            IngestionStatus.UNREADABLE,
            f"permission denied reading file: {file_path.name}",
        )
    except OSError as e:
        return (
            False,
            None,
            file_size,
            IngestionStatus.UNREADABLE,
            f"document could not be opened: {e.strerror or str(e)}",
        )

    return (True, header_bytes, file_size, None, None)
