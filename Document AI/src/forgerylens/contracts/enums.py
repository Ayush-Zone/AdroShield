"""Enumerations for ForgeryLens contracts and ingestion status."""

from enum import Enum


class DocumentFormat(str, Enum):
    """Supported document formats."""

    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    UNKNOWN = "unknown"


class IngestionStatus(str, Enum):
    """Status outcomes for document ingestion and preliminary validation."""

    VALID = "valid"
    CORRUPT = "corrupt"
    UNSUPPORTED = "unsupported"
    UNREADABLE = "unreadable"
    EMPTY = "empty"
