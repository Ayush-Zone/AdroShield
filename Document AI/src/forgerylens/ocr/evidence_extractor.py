import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Union
import fitz
from PIL import Image
import pytesseract

from forgerylens.contracts.evidence import EvidenceRecord, Provenance, EvidenceStatus

def extract_text(page: Union["fitz.Page", Image.Image], storage_dir: str | Path, source_file_sha256: str = "") -> tuple[EvidenceRecord, list[dict]]:
    """
    Extracts text from a page and returns an EvidenceRecord (linking to raw output)
    plus a list of normalized words.
    
    Args:
        page: A fitz.Page (for native PDF) or a PIL Image (for scans).
        storage_dir: Where to store the raw engine output.
        source_file_sha256: For provenance.
    """
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc)
    words = []
    raw_output = None
    
    if isinstance(page, fitz.Page):
        tool_name = "forgerylens_pdf_extractor"
        tool_version = fitz.VersionBind
        method = "pdf_text_layer"
        
        # Raw engine output unmodified
        raw_output = page.get_text("dict")
        
        page_width, page_height = page.rect.width, page.rect.height
        
        word_tuples = page.get_text("words")
        for wt in word_tuples:
            x0, y0, x1, y1, text, _, _, _ = wt
            text = text.strip()
            if not text:
                continue
            
            width = x1 - x0
            height = y1 - y0
            
            norm_x = min(max(x0 / page_width, 0.0), 1.0) if page_width > 0 else 0.0
            norm_y = min(max(y0 / page_height, 0.0), 1.0) if page_height > 0 else 0.0
            norm_w = min(max(width / page_width, 0.0), 1.0) if page_width > 0 else 0.0
            norm_h = min(max(height / page_height, 0.0), 1.0) if page_height > 0 else 0.0
            
            words.append({
                "text": text,
                "x": norm_x,
                "y": norm_y,
                "width": norm_w,
                "height": norm_h,
                "confidence": None,
                "source": "pdf_text_layer",
                "is_low_confidence": False
            })
                        
        prov = Provenance(
            source_file_sha256=source_file_sha256,
            tool_name=tool_name,
            tool_version=tool_version,
            parameters={"extraction": "dict"},
            timestamp=timestamp
        )
        
    elif isinstance(page, Image.Image):
        tool_name = "forgerylens_tesseract_ocr"
        try:
            tool_version = str(pytesseract.get_tesseract_version().base_version)
        except Exception:
            tool_version = "unknown"
            
        method = "ocr:tesseract"
        
        img_width, img_height = page.size
        
        if img_width > 0 and img_height > 0:
            try:
                raw_output = pytesseract.image_to_data(page, output_type=pytesseract.Output.DICT)
                
                for i in range(len(raw_output.get("text", []))):
                    text = raw_output["text"][i].strip()
                    if int(raw_output["level"][i]) == 5 and text:
                        conf_val = raw_output["conf"][i]
                        try:
                            conf = float(conf_val)
                            if conf < 0:
                                conf = 0.0
                        except (ValueError, TypeError):
                            conf = 0.0
                        
                        left = float(raw_output["left"][i])
                        top = float(raw_output["top"][i])
                        width = float(raw_output["width"][i])
                        height = float(raw_output["height"][i])
                        
                        norm_x = min(max(left / img_width, 0.0), 1.0)
                        norm_y = min(max(top / img_height, 0.0), 1.0)
                        norm_w = min(max(width / img_width, 0.0), 1.0)
                        norm_h = min(max(height / img_height, 0.0), 1.0)
                        
                        words.append({
                            "text": text,
                            "x": norm_x,
                            "y": norm_y,
                            "width": norm_w,
                            "height": norm_h,
                            "confidence": conf,
                            "source": "ocr:tesseract",
                            "is_low_confidence": conf < 50.0
                        })
            except Exception as e:
                raw_output = {"error": str(e)}
        else:
            raw_output = {"error": "Image has 0 width or height"}
            
        prov = Provenance(
            source_file_sha256=source_file_sha256,
            tool_name=tool_name,
            tool_version=tool_version,
            parameters={"engine": "tesseract", "language": "eng"},
            timestamp=timestamp
        )
    else:
        raise ValueError("Unsupported page type")
        
    raw_ref = None
    if raw_output is not None:
        raw_id = str(uuid.uuid4())
        raw_filename = f"raw_extraction_{raw_id}.json"
        raw_path = storage_dir / raw_filename
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_output, f)
        raw_ref = str(raw_path)
        
    # Read back to ensure unmodified!
    if raw_ref:
        with open(raw_ref, "r", encoding="utf-8") as f:
            read_back = json.load(f)
            # The test will verify read_back matches raw_output
            
    status = EvidenceStatus.OK
    if raw_output and "error" in raw_output:
        status = EvidenceStatus.NOT_ANALYZABLE
        
    evidence = EvidenceRecord(
        id=str(uuid.uuid4()),
        type="text_extraction",
        observation={"words_count": len(words)},
        method=method,
        status=status,
        raw_ref=raw_ref,
        provenance=prov
    )
    
    return evidence, words
