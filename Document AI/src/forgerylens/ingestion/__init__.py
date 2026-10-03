"""Ingestion package for ForgeryLens."""

from forgerylens.ingestion.reader import ingest_document
from forgerylens.ingestion.mime import detect_document_format
from forgerylens.ingestion.validator import validate_file_sanity

__all__ = [
    "ingest_document",
    "detect_document_format",
    "validate_file_sanity",
]
