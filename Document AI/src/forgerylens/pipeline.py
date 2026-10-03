import os
import uuid
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List
import fitz

from forgerylens.contracts.document import DocumentFormat
from forgerylens.contracts.enums import IngestionStatus
from forgerylens.contracts.structured import DocumentType
from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance, EvidenceBundle

from forgerylens.ingestion.reader import ingest_document
from forgerylens.ocr.orchestrator import extract_document_text
from forgerylens.ocr.evidence_extractor import extract_text
from forgerylens.classification.classifier import classify_document
from forgerylens.packs.invoice.extractor import extract_invoice_pack
from forgerylens.packs.invoice.consistency import run_all_consistency_checks
from forgerylens.forensics.metadata import analyze_pdf, analyze_image
from forgerylens.forensics.pixels import analyze_pixels

STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "forgerylens_storage"
PIPELINE_VERSION = "1.0.0"

def run_pipeline(file_path: str) -> EvidenceBundle:
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
    # 1. Ingestion (Phase 2)
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

    # 2. OCR (Phase 3)
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
                evidence_list.append(EvidenceRecord(
                    id=str(uuid.uuid4()),
                    type="text_extraction",
                    status=EvidenceStatus.OK,
                    observation={"pages_extracted": len(ocr_result.pages)},
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

    # 3. Classification (Phase 4)
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

    # 4. Invoice Consistency (Phase 5)
    is_invoice = (classification_record and classification_record.status == EvidenceStatus.OK 
                  and classification_record.observation.get("document_type") == DocumentType.INVOICE.value)
                  
    if is_invoice and ocr_result and ocr_result.status == IngestionStatus.VALID:
        try:
            pack = extract_invoice_pack(ocr_result)
            ref_date = datetime.now().date()
            cons_records = run_all_consistency_checks(pack, ref_date)
            for r in cons_records:
                r.provenance.source_file_sha256 = source_sha256
                evidence_list.append(r)
        except Exception as e:
            evidence_list.append(EvidenceRecord(
                id=str(uuid.uuid4()),
                type="invoice_consistency",
                status=EvidenceStatus.NOT_ANALYZABLE,
                observation={"reasons": [f"Extraction failed: {e}"]},
                method="invoice_consistency",
                provenance=doc_prov
            ))

    # 5. Metadata Forensics (Phase 9)
    try:
        if not ingest_failed and ingested_doc and ingested_doc.format == DocumentFormat.PDF:
            raw_meta, meta_records = analyze_pdf(file_path)
        else:
            raw_meta, meta_records = analyze_image(file_path)
            
        for r in meta_records:
            r.provenance.source_file_sha256 = source_sha256
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

    # 6. Pixel Forensics (Phase 9)
    try:
        if not ingest_failed and ingested_doc and ingested_doc.format == DocumentFormat.PDF:
            pdf_doc = fitz.open(file_path)
            for page_idx in range(len(pdf_doc)):
                page = pdf_doc[page_idx]
                pix = page.get_pixmap(dpi=150)
                raster_path = doc_storage_dir / f"page_{page_idx}.png"
                pix.save(str(raster_path))
                
                raw_map, pixel_records = analyze_pixels(str(raster_path), is_pdf_rasterized=True)
                if raw_map:
                    map_path = doc_storage_dir / f"ela_map_page_{page_idx}.png"
                    with open(map_path, "wb") as f:
                        f.write(raw_map)
                    for r in pixel_records:
                        r.raw_ref = str(map_path)
                        r.provenance.source_file_sha256 = source_sha256
                        evidence_list.append(r)
                else:
                    for r in pixel_records:
                        r.provenance.source_file_sha256 = source_sha256
                        evidence_list.append(r)
            pdf_doc.close()
        else:
            raw_map, pixel_records = analyze_pixels(file_path, is_pdf_rasterized=False)
            if raw_map:
                map_path = doc_storage_dir / f"ela_map.png"
                with open(map_path, "wb") as f:
                    f.write(raw_map)
                for r in pixel_records:
                    r.raw_ref = str(map_path)
                    r.provenance.source_file_sha256 = source_sha256
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
