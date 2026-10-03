import uuid
import io
import cv2
import numpy as np
from typing import Dict, Any, List, Tuple
from PIL import Image

from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance
from forgerylens.contracts.spatial import normalize_bbox

# --- Named Constants ---

# Analyzability Cutoffs
MIN_RESOLUTION = (100, 100)
MIN_PIXEL_COUNT = MIN_RESOLUTION[0] * MIN_RESOLUTION[1]
MIN_VARIANCE = 5.0
MIN_JPEG_QUALITY = 50

# ELA Constants
ELA_RESAVE_QUALITY = 90
ELA_SEGMENTATION_THRESHOLD = 40  # Region grouping, not a forgery decision
MAX_REGIONS_EMITTED = 10

ELA_LIMITATIONS_TEXT = (
    "ELA reacts to normal compression, re-saving, and sharp text edges; "
    "it can produce regions on unedited images and miss real edits; it is a weak indicator only."
)

def _create_evidence(check_name: str, status: EvidenceStatus, observation: Dict[str, Any], raw_ref: str, parameters: Dict[str, Any] = None) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(uuid.uuid4()),
        type=f"forensic_{check_name}",
        observation=observation,
        method="rule_based",
        status=status,
        provenance=Provenance(
            source_file_sha256="unknown", # Expected to be updated by caller
            tool_name="forgerylens_pixels",
            tool_version="1.0",
            parameters=parameters or {}
        )
    )

def _estimate_jpeg_quality(img: Image.Image) -> Any:
    # Attempt to read quality from quantization tables
    if img.format != "JPEG":
        return "unknown"
        
    try:
        # A simple estimation based on Pillow internals or if it's stored in info
        q = img.info.get("quality", "unknown")
        if q != "unknown":
            return q
            
        # Pillow doesn't expose a straightforward quality property directly from QT
        # If we can't extract it easily, return 'unknown'
        return "unknown"
    except Exception:
        return "unknown"

def assess_analyzability(file_path: str, is_pdf_rasterized: bool = False) -> Tuple[str, List[str], EvidenceRecord]:
    raw_ref = None
    reasons = []
    status = "analyzable"
    evidence_status = EvidenceStatus.OK
    
    try:
        with Image.open(file_path) as img:
            fmt = img.format
            w, h = img.size
            
            # Reject non-JPEG or PDF rasterized immediately
            if is_pdf_rasterized:
                return "not_analyzable", ["no JPEG compression history (PDF input)"], _create_evidence(
                    "ela_applicability", EvidenceStatus.NOT_ANALYZABLE,
                    {"analyzability": "not_analyzable", "reasons": ["no JPEG compression history (PDF input)"]},
                    raw_ref
                )
            if fmt != "JPEG":
                reason_str = f"no JPEG compression history ({fmt} input)"
                return "not_analyzable", [reason_str], _create_evidence(
                    "ela_applicability", EvidenceStatus.NOT_ANALYZABLE,
                    {"analyzability": "not_analyzable", "reasons": [reason_str]},
                    raw_ref
                )
                
            # Resolution check
            if w * h < MIN_PIXEL_COUNT or w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
                status = "not_analyzable"
                evidence_status = EvidenceStatus.NOT_ANALYZABLE
                reasons.append(f"resolution ({w}x{h}) is below minimum {MIN_RESOLUTION[0]}x{MIN_RESOLUTION[1]}")
                
            # Variance check (flat image)
            gray = img.convert("L")
            stat_arr = np.array(gray)
            variance = np.var(stat_arr)
            if variance < MIN_VARIANCE:
                status = "not_analyzable"
                evidence_status = EvidenceStatus.NOT_ANALYZABLE
                reasons.append(f"variance {variance:.2f} is below minimum {MIN_VARIANCE} (flat/blank image)")
                
    except Exception as e:
        return "not_analyzable", [str(e)], _create_evidence(
            "ela_applicability", EvidenceStatus.NOT_ANALYZABLE,
            {"analyzability": "not_analyzable", "reasons": [str(e)]},
            raw_ref
        )
        
    obs = {
        "analyzability": status,
        "reasons": reasons if reasons else ["acceptable"],
        "jpeg_quality": "unknown",
        "jpeg_quality_reason": "quality not exposed by Pillow"
    }
    
    return status, reasons, _create_evidence("ela_applicability", evidence_status, obs, raw_ref)


def run_ela(file_path: str) -> Tuple[bytes, List[EvidenceRecord]]:
    raw_ref = None
    records = []
    
    # 1. Load Original
    orig_img = Image.open(file_path).convert("RGB")
    
    # 2. Resave in memory
    buffer = io.BytesIO()
    orig_img.save(buffer, format="JPEG", quality=ELA_RESAVE_QUALITY)
    buffer.seek(0)
    resaved_img = Image.open(buffer).convert("RGB")
    
    # 3. Compute difference (ELA map)
    orig_arr = np.array(orig_img, dtype=np.int16)
    resaved_arr = np.array(resaved_img, dtype=np.int16)
    
    diff = np.abs(orig_arr - resaved_arr)
    # Scale difference map for thresholding
    # Scale max diff to 255
    max_diff = np.max(diff)
    if max_diff == 0:
        scale = 1
    else:
        scale = 255.0 / max_diff
    
    scaled_diff = (diff * scale).astype(np.uint8)
    # Convert to grayscale for thresholding
    gray_diff = cv2.cvtColor(scaled_diff, cv2.COLOR_RGB2GRAY)
    
    # Store raw map (unmodified)
    raw_map_buffer = io.BytesIO()
    raw_map_img = Image.fromarray(diff.astype(np.uint8)) # Keep raw byte values
    raw_map_img.save(raw_map_buffer, format="PNG")
    raw_map_bytes = raw_map_buffer.getvalue()
    
    # 4. Thresholding and Contours
    _, thresh = cv2.threshold(gray_diff, ELA_SEGMENTATION_THRESHOLD, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    params = {
        "resave_quality": ELA_RESAVE_QUALITY,
        "segmentation_threshold": ELA_SEGMENTATION_THRESHOLD,
        "cv2_version": cv2.__version__
    }
    
    # 5. Extract Regions
    # Sort contours by area descending to get most significant first
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    emitted = 0
    for c in contours:
        if emitted >= MAX_REGIONS_EMITTED:
            break
            
        x, y, w, h = cv2.boundingRect(c)
        # Bounding box coordinates: top-left x, y, width, height
        box_diff = diff[y:y+h, x:x+w]
        magnitude = float(np.sum(box_diff))
        
        img_w, img_h = orig_img.size
        
        try:
            nx, ny, nw, nh = normalize_bbox(float(x), float(y), float(w), float(h), float(img_w), float(img_h))
        except ValueError as e:
            records.append(_create_evidence(
                "ela_region", EvidenceStatus.NOT_ANALYZABLE, 
                {"reason": f"Box normalization failed: {e}", "bbox_px": {"x": x, "y": y, "width": w, "height": h}, "image_size_px": {"w": img_w, "h": img_h}},
                raw_ref, parameters=params
            ))
            emitted += 1
            continue
        
        obs = {
            "bounding_box": {"x": nx, "y": ny, "width": nw, "height": nh},
            "bbox_px": {"x": x, "y": y, "width": w, "height": h},
            "image_size_px": {"w": img_w, "h": img_h},
            "raw_difference_magnitude": magnitude,
            "confidence": None,
            "limitations": ELA_LIMITATIONS_TEXT
        }
        
        if emitted == MAX_REGIONS_EMITTED - 1 and len(contours) > MAX_REGIONS_EMITTED:
            obs["note"] = f"MAX_REGIONS_EMITTED cap ({MAX_REGIONS_EMITTED}) reached."
            
        records.append(_create_evidence("ela_region", EvidenceStatus.OK, obs, raw_ref, parameters=params))
        emitted += 1
        
    return raw_map_bytes, records

def analyze_pixels(file_path: str, is_pdf_rasterized: bool = False) -> Tuple[bytes, List[EvidenceRecord]]:
    status, reasons, analyzability_record = assess_analyzability(file_path, is_pdf_rasterized)
    
    if status in ("not_analyzable", "degraded"):
        return b"", [analyzability_record]
        
    raw_map_bytes, ela_records = run_ela(file_path)
    
    return raw_map_bytes, [analyzability_record] + ela_records
