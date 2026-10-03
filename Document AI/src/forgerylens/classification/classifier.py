import uuid
import re
from typing import Dict, List, Tuple

from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance
from forgerylens.contracts.structured import DocumentType

CUES: Dict[DocumentType, List[str]] = {
    DocumentType.INVOICE: ["invoice", "receipt", "tax invoice", "subtotal", "amount due", "vendor", "grand total", "qty"],
    DocumentType.ID_DOCUMENT: ["passport", "id card", "identity card", "driver license", "driving licence", "date of birth", "dob", "nationality", "pan card", "aadhaar", "driver's license", "expires"],
    DocumentType.MEDICAL_BILL: ["hospital", "clinic", "patient", "medical", "treatment", "doctor", "prescription", "pharmacy", "discharge", "consultation", "surgery", "bill"],
    DocumentType.POLICE_REPORT: ["police", "fir", "first information report", "station", "inspector", "officer", "complaint", "incident", "investigation", "jurisdiction"]
}

def classify_document(text: str, source_sha256: str = "unknown") -> EvidenceRecord:
    """Classify document text using simple keyword heuristics."""
    text_lower = text.lower()
    scores: Dict[DocumentType, int] = {}
    matched_cues: Dict[DocumentType, List[str]] = {}
    
    for doc_type, keywords in CUES.items():
        matched = []
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                matched.append(kw)
        
        if matched:
            scores[doc_type] = len(matched)
            matched_cues[doc_type] = matched
            
    # Sort by score descending
    sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    prov = Provenance(
        source_file_sha256=source_sha256,
        tool_name="forgerylens_classifier",
        tool_version="1.0",
        parameters={"rule_based": True}
    )
    
    # Gibberish / unknown case
    if not sorted_types:
        return EvidenceRecord(
            id=str(uuid.uuid4()),
            type="document_classification",
            observation={"document_type": DocumentType.UNKNOWN.value, "cues": {}},
            method="keyword_heuristics",
            status=EvidenceStatus.OK,
            provenance=prov
        )
        
    top_type, top_score = sorted_types[0]
    
    # Ambiguous case: if top 2 score very closely
    if len(sorted_types) > 1:
        runner_up_type, runner_up_score = sorted_types[1]
        
        if top_score - runner_up_score <= 1:
            return EvidenceRecord(
                id=str(uuid.uuid4()),
                type="document_classification",
                observation={
                    "document_type": DocumentType.AMBIGUOUS.value,
                    "candidates": [top_type.value, runner_up_type.value],
                    "cues": {
                        top_type.value: matched_cues[top_type],
                        runner_up_type.value: matched_cues[runner_up_type]
                    }
                },
                method="keyword_heuristics",
                status=EvidenceStatus.AMBIGUOUS,
                provenance=prov
            )
            
    # Clear winner
    return EvidenceRecord(
        id=str(uuid.uuid4()),
        type="document_classification",
        observation={
            "document_type": top_type.value,
            "cues": matched_cues[top_type]
        },
        method="keyword_heuristics",
        status=EvidenceStatus.OK,
        provenance=prov
    )
