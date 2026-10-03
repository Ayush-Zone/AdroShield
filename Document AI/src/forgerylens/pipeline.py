import os
import uuid
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from forgerylens.contracts.document import DocumentFormat
from forgerylens.contracts.enums import IngestionStatus
from forgerylens.contracts.structured import DocumentType
from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance, EvidenceBundle
from forgerylens.contracts.storage import make_artifact_ref
from forgerylens.ingestion.reader import ingest_document
from forgerylens.ocr.orchestrator import extract_document_text
from forgerylens.classification.classifier import classify_document
from forgerylens.packs.invoice.consistency import run_all_consistency_checks
from forgerylens.forensics.metadata import analyze_pdf, analyze_image
from forgerylens.forensics.pixels import analyze_pixels
from forgerylens.extraction.parser import parse_document
from forgerylens.normalization.normalizer import normalize_document

STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "forgerylens_storage"
PIPELINE_VERSION = "1.0.0"

def run_pipeline(file_path: str, *, reference_date: Optional[datetime.date] = None) -> EvidenceBundle:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Missing file: {file_path}")

    with open(file_path, "rb") as f:
        file_bytes = f.read()
    source_sha256 = hashlib.sha256(file_bytes).hexdigest()

    doc_storage_dir = STORAGE_ROOT / source_sha256
    doc_storage_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    doc_prov = Provenance(
        source_file_sha256=source_sha256,
        tool_name="forgerylens_pipeline",
        tool_version=PIPELINE_VERSION,
        parameters={},
        timestamp=timestamp
    )

    evidence_list: List[EvidenceRecord] = []
    # 1. Ingestion
    ingested_doc = ingest_document(file_path)
    if ingested_doc.status != IngestionStatus.VALID:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="ingestion",
            status=EvidenceStatus.NOT_ANALYZABLE,
            observation={"reasons": ingested_doc.errors or ["Ingestion failed"]},
            method="ingestion",
            provenance=doc_prov
        ))
        ingest_failed = True
    else:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="ingestion",
            status=EvidenceStatus.OK,
            observation={"pages": ingested_doc.page_count, "format": ingested_doc.format.value},
            method="ingestion",
            provenance=doc_prov
        ))
        ingest_failed = False

    # 2. Text Extraction
    ocr_result = None
    if ingest_failed:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="text_extraction",
            status=EvidenceStatus.NOT_ANALYZABLE,
            observation={"reasons": ["upstream failed: ingest"]},
            method="orchestrator",
            provenance=doc_prov
        ))
    else:
        try:
            ocr_result = extract_document_text(ingested_doc)
            if ocr_result.status != IngestionStatus.VALID:
                evidence_list.append(EvidenceRecord(
                    id=str(uuid.uuid4()),
                    type="text_extraction",
                    status=EvidenceStatus.NOT_ANALYZABLE,
                    observation={"errors": ocr_result.errors},
                    method="orchestrator",
                    provenance=doc_prov
                ))
            else:
                pages_meta = []
                for p in ocr_result.pages:
                    pages_meta.append({
                        "page_number": p.page_number,
                        "source": p.extraction_method.value,
                        "word_count": len(p.words),
                        "ocr_fallback_used": p.extraction_method.value == "TESSERACT_OCR" and ingested_doc.format == DocumentFormat.PDF
                    })
                evidence_list.append(EvidenceRecord(
                    id=str(uuid.uuid4()),
                    type="text_extraction",
                    status=EvidenceStatus.OK,
                    observation={"pages_extracted": len(ocr_result.pages), "pages": pages_meta},
                    method="orchestrator",
                    provenance=doc_prov
                ))
        except Exception as e:
            ocr_result = None
            evidence_list.append(EvidenceRecord(
                id=str(uuid.uuid4()),
                type="text_extraction",
                status=EvidenceStatus.NOT_ANALYZABLE,
                observation={"reasons": [str(e)]},
                method="orchestrator",
                provenance=doc_prov
            ))

    # 3. Document Classification
    classification_record = None
    if not ocr_result or ocr_result.status != IngestionStatus.VALID:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="classification",
            status=EvidenceStatus.NOT_ANALYZABLE,
            observation={"reasons": ["upstream failed: text_extraction"]},
            method="classification",
            provenance=doc_prov
        ))
    else:
        full_text = " ".join([p.full_text for p in ocr_result.pages])
        classification_record = classify_document(full_text, source_sha256)
        evidence_list.append(classification_record)

    # 4. Structured Extraction, Normalization & Consistency Checks
    # Avoid silent skips (AF-1)
    if classification_record:
        doc_type_val = classification_record.observation.get("document_type")
        cues = classification_record.observation.get("cues")
        candidates = classification_record.observation.get("candidates")

        is_invoice = (classification_record.status == EvidenceStatus.OK and doc_type_val == DocumentType.INVOICE.value)

        if not is_invoice:
            reason = f"Document type is {doc_type_val}"
            if doc_type_val == DocumentType.AMBIGUOUS.value:
                reason += f", candidates: {candidates}"
            if cues:
                reason += f", cues: {cues}"

            evidence_list.append(EvidenceRecord(
                id=str(uuid.uuid4()),
                type="pack_orchestration",
                status=EvidenceStatus.NOT_ANALYZABLE,
                observation={"reasons": [f"Extraction and consistency checks NOT run: {reason}"]},
                method="pipeline",
                provenance=doc_prov
            ))
        elif ocr_result and ocr_result.status == IngestionStatus.VALID:
            try:
                structured_invoice = parse_document(ocr_result)
                normalized_invoice = normalize_document(structured_invoice)

                cons_records = run_all_consistency_checks(normalized_invoice, reference_date)
                for r in cons_records:
                    r.provenance.source_file_sha256 = source_sha256
                    evidence_list.append(r)
            except Exception as e:
                evidence_list.append(EvidenceRecord(
                    id=str(uuid.uuid4()),
                    type="pack_orchestration",
                    status=EvidenceStatus.NOT_ANALYZABLE,
                    observation={"reasons": [f"Extraction failed: {e}"]},
                    method="pipeline",
                    provenance=doc_prov
                ))

    # 5. Metadata Forensics
    try:
        if not ingest_failed and ingested_doc and ingested_doc.format == DocumentFormat.PDF:
            raw_meta, meta_records = analyze_pdf(file_path)
        else:
            raw_meta, meta_records = analyze_image(file_path)

        meta_path = doc_storage_dir / "metadata_raw.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(raw_meta, f, indent=2)
        meta_ref = make_artifact_ref(source_sha256, "metadata_raw.json")

        for r in meta_records:
            r.provenance.source_file_sha256 = source_sha256
            if hasattr(r, "raw_ref") and r.raw_ref is None:
                r.raw_ref = meta_ref
            evidence_list.append(r)
    except Exception as e:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="forensic_metadata",
            status=EvidenceStatus.NOT_ANALYZABLE,
            observation={"reasons": [str(e)]},
            method="rule_based",
            provenance=doc_prov
        ))

    # 6. Pixel Forensics
    try:
        if not ingest_failed and ingested_doc and ingested_doc.format == DocumentFormat.PDF:
            # FL-03: No rasterization, no ELA for PDFs. Just emit one record.
            pdf_ela_record = EvidenceRecord(
                id=str(uuid.uuid4()),
                type="forensic_ela_applicability",
                status=EvidenceStatus.NOT_ANALYZABLE,
                observation={"analyzability": "not_analyzable", "reasons": ["no JPEG compression history (PDF input)"], "jpeg_quality": "unknown", "jpeg_quality_reason": "quality not exposed by Pillow"},
                method="rule_based",
                provenance=doc_prov,
                raw_ref=None
            )
            evidence_list.append(pdf_ela_record)
        else:
            raw_map, pixel_records = analyze_pixels(file_path, is_pdf_rasterized=False)
            if raw_map:
                map_path = doc_storage_dir / "ela_map.png"
                with open(map_path, "wb") as f:
                    f.write(raw_map)
                ela_ref = make_artifact_ref(source_sha256, "ela_map.png")
                for r in pixel_records:
                    r.provenance.source_file_sha256 = source_sha256
                    if hasattr(r, "raw_ref") and r.raw_ref is None:
                        r.raw_ref = ela_ref
                    evidence_list.append(r)
            else:
                for r in pixel_records:
                    r.provenance.source_file_sha256 = source_sha256
                    evidence_list.append(r)
    except Exception as e:
        evidence_list.append(EvidenceRecord(
            id=str(uuid.uuid4()),
            type="forensic_image_analyzability",
            status=EvidenceStatus.NOT_ANALYZABLE,
            observation={"reasons": [str(e)]},
            method="rule_based",
            provenance=doc_prov
        ))

    return EvidenceBundle(
        document_provenance=doc_prov,
        evidence=evidence_list
    )
