from typing import Dict, Any
from forgerylens.contracts.evidence import EvidenceBundle

def generate_demo_ui_payload(bundle: EvidenceBundle) -> Dict[str, Any]:
    """
    Transforms the backend ForgeryLens EvidenceBundle into a UI-friendly payload
    with evidence passthrough and strictly derived findings.
    """
    evidence_list = []
    findings = []

    for record in bundle.evidence:
        # Pass through exactly as is
        record_dict = {
            "id": record.id,
            "type": record.type,
            "observation": record.observation,
            "location": record.location.model_dump() if hasattr(record.location, "model_dump") else record.location.dict() if hasattr(record.location, "dict") else record.location.__dict__ if record.location else None,
            "method": record.method,
            "confidence": getattr(record, "confidence", None),
            "status": record.status.value if hasattr(record.status, "value") else str(record.status),
            "limitations": getattr(record, "limitations", None),
            "raw_ref": record.raw_ref
        }

        evidence_list.append(record_dict)

        # Deterministic rules for findings
        obs = record.observation
        if isinstance(obs, dict):
            # 1. ELA regions
            if record.type == "forensic_ela_region":
                mag = obs.get("raw_difference_magnitude", 0)
                findings.append({
                    "finding_id": f"fnd_{record.id}",
                    "summary": f"ELA region detected with magnitude {mag}",
                    "evidence_ids": [record.id]
                })

            # 2. Consistency checks mismatches
            # In Phase 2, consistency check invalid results output 'result'='mismatch' or 'invalid'
            if record.type.startswith("consistency_check"):
                res = obs.get("result", "")
                if res == "mismatch" or obs.get("status") == "invalid":
                    findings.append({
                        "finding_id": f"fnd_{record.id}",
                        "summary": f"Consistency mismatch detected in {record.type}",
                        "evidence_ids": [record.id]
                    })

    # document_provenance serialization logic
    prov_dict = {}
    if hasattr(bundle.document_provenance, "to_dict"):
        prov_dict = bundle.document_provenance.to_dict()
    elif hasattr(bundle.document_provenance, "__dict__"):
        prov_dict = bundle.document_provenance.__dict__.copy()
        if "timestamp" in prov_dict and hasattr(prov_dict["timestamp"], "isoformat"):
            prov_dict["timestamp"] = prov_dict["timestamp"].isoformat()

    return {
        "document_provenance": prov_dict,
        "evidence": evidence_list,
        "findings": findings
    }
