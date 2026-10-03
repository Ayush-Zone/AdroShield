import fitz
from PIL import Image
from pathlib import Path
import shutil
import uuid
import io
from forgerylens.contracts.evidence import EvidenceRecord, Provenance, EvidenceStatus
from forgerylens.utils.hash import calculate_file_sha256
from datetime import datetime, timezone

SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg"
}

def ingest_document_evidence(filepath: str | Path, storage_dir: str | Path) -> tuple[EvidenceRecord, list[Image.Image]]:
    filepath = Path(filepath)
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    tool_name = "forgerylens_evidence_ingestor"
    tool_version = "1.0.0"
    params = {"fixed_dpi": 150}
    
    if not filepath.exists():
        prov = Provenance(
            source_file_sha256="",
            tool_name=tool_name,
            tool_version=tool_version,
            parameters=params,
            timestamp=datetime.now(timezone.utc)
        )
        return EvidenceRecord(
            id=str(uuid.uuid4()),
            type="document_ingestion",
            observation={"error": "File does not exist"},
            method="file_system",
            status=EvidenceStatus.NOT_ANALYZABLE,
            limitations="Cannot analyze missing file",
            provenance=prov
        ), []

    sha256 = calculate_file_sha256(filepath)
    ext = filepath.suffix.lower()
    
    prov = Provenance(
        source_file_sha256=sha256,
        tool_name=tool_name,
        tool_version=tool_version,
        parameters=params,
        timestamp=datetime.now(timezone.utc)
    )

    if ext not in SUPPORTED_TYPES:
        return EvidenceRecord(
            id=str(uuid.uuid4()),
            type="document_ingestion",
            observation={"error": f"Unsupported file type: {ext}"},
            method="mime_check",
            status=EvidenceStatus.NOT_ANALYZABLE,
            limitations="Only PDF, PNG, and JPEG are supported",
            provenance=prov
        ), []

    safe_filename = f"{sha256}{ext}"
    stored_path = storage_dir / safe_filename
    if not stored_path.exists():
        shutil.copy2(filepath, stored_path)

    pages: list[Image.Image] = []
    metadata = {
        "format": SUPPORTED_TYPES[ext],
        "file_size": filepath.stat().st_size,
        "page_count": 0,
        "dimensions": []
    }
    
    try:
        if ext == ".pdf":
            doc = fitz.open(filepath)
            metadata["page_count"] = len(doc)
            for page in doc:
                pix = page.get_pixmap(dpi=params["fixed_dpi"])
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                pages.append(img)
                metadata["dimensions"].append((img.width, img.height))
            doc.close()
        else:
            img = Image.open(filepath)
            img.verify()
            img = Image.open(filepath)
            img.load()
            pages.append(img)
            metadata["page_count"] = 1
            metadata["dimensions"].append((img.width, img.height))
            
    except Exception as e:
        return EvidenceRecord(
            id=str(uuid.uuid4()),
            type="document_ingestion",
            observation={"error": f"Corrupt or unreadable file: {str(e)}"},
            method="parsing",
            status=EvidenceStatus.NOT_ANALYZABLE,
            raw_ref=str(stored_path),
            provenance=prov
        ), []

    if metadata["page_count"] == 0:
        return EvidenceRecord(
            id=str(uuid.uuid4()),
            type="document_ingestion",
            observation={"error": "Document contains no pages"},
            method="parsing",
            status=EvidenceStatus.NOT_ANALYZABLE,
            raw_ref=str(stored_path),
            provenance=prov
        ), []

    return EvidenceRecord(
        id=str(uuid.uuid4()),
        type="document_ingestion",
        observation=metadata,
        method="ingestion_pipeline",
        status=EvidenceStatus.OK,
        raw_ref=str(stored_path),
        provenance=prov
    ), pages
