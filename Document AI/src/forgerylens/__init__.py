"""ForgeryLens — Document Intelligence component of ADROSHIELD."""

from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.document import PageInfo, IngestedDocument
from forgerylens.ingestion.reader import ingest_document

__version__ = "0.2.0"

__all__ = [
    "ingest_document",
    "IngestedDocument",
    "PageInfo",
    "DocumentFormat",
    "IngestionStatus",
]
