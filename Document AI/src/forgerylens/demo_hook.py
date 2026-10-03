from typing import Dict, Any
from forgerylens.contracts.evidence import EvidenceBundle

def generate_demo_ui_payload(bundle: EvidenceBundle) -> Dict[str, Any]:
    """
    Transforms the backend ForgeryLens EvidenceBundle into a flat, 
    UI-friendly payload with bounding boxes and messages for a frontend demo overlay.
    """
    ui_findings = []
    
    for record in bundle.evidence:
        # Skip routine OK records unless they are specific consistency passes
        if record.status == "ok" and not record.type.startswith("consistency_check"):
            continue
            
        finding = {
            "id": record.id,
            "type": record.type,
            "status": record.status.value,
            "method": record.method,
            "message": "",
            "regions": [], # List of {page, x, y, width, height}
            "raw_image_url": record.raw_ref # E.g., for ELA map overlays
        }
        
        # Extract messages and regions based on observation structure
        obs = record.observation
        if isinstance(obs, dict):
            # 1. Pixel/ELA regions
            if "bounding_box" in obs:
                box = obs["bounding_box"]
                page_num = obs.get("page", 1)  # Default to 1 if missing
                finding["regions"].append({
                    "page": page_num,
                    "x": box.get("x", 0.0),
                    "y": box.get("y", 0.0),
                    "width": box.get("width", 0.0),
                    "height": box.get("height", 0.0)
                })
                score = obs.get("suspicious_score", 0.0)
                finding["message"] = f"Anomalous pixel region detected (Score: {score:.2f})"
            
            # 2. Consistency checks
            elif "values_compared" in obs:
                res = obs.get("result", "unknown")
                if res == "mismatch":
                    finding["message"] = f"Consistency mismatch detected in {record.type}"
                elif res in ("exact", "within_rounding"):
                    finding["message"] = f"Consistency verified: {record.type}"
                else:
                    finding["message"] = f"Consistency check: {res}"
                    
                # If region data was piped through (currently raw_value and parsed are there, but we can accommodate future region propagation)
                # Actually, consistency checks in Phase 6 don't easily expose bounding boxes in EvidenceRecord observation yet.
                # But we provide the schema structure for it.
            
            # 3. Metadata/General Errors
            elif "reasons" in obs:
                finding["message"] = " | ".join(obs["reasons"])
            elif "errors" in obs:
                finding["message"] = " | ".join(obs["errors"])
            else:
                finding["message"] = f"Finding from {record.type}"
                
        else:
            finding["message"] = str(obs)
            
        ui_findings.append(finding)
        
    return {
        "document_sha256": bundle.document_provenance.source_file_sha256,
        "timestamp": bundle.document_provenance.timestamp.isoformat(),
        "tool_version": bundle.document_provenance.tool_version,
        "findings": ui_findings
    }
