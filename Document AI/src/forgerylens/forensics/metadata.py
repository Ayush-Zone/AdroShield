import uuid
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple
from forgerylens.contracts.evidence import EvidenceRecord, EvidenceStatus, Provenance

try:
    import fitz
except ImportError:
    fitz = None

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    Image = None

def _create_evidence(check_name: str, status: EvidenceStatus, observation: Dict[str, Any], raw_ref: str, parameters: Dict[str, Any] = None) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(uuid.uuid4()),
        type=f"forensic_{check_name}",
        observation=observation,
        method="rule_based",
        status=status,
        provenance=Provenance(
            source_file_sha256="unknown", # Expected to be updated by caller
            tool_name="forgerylens_forensics",
            tool_version="1.0",
            parameters=parameters or {}
        )
    )

def _parse_pdf_date(pdf_date: str) -> datetime:
    """Parses PDF date format D:YYYYMMDDHHmmSSOHH'mm'"""
    if not pdf_date or not pdf_date.startswith("D:"):
        return None
    # Strip the D: and any timezone info for a naive compare
    clean = re.sub(r'[^0-9]', '', pdf_date[2:16])
    if len(clean) == 14:
        try:
            return datetime.strptime(clean, "%Y%m%d%H%M%S")
        except ValueError:
            return None
    return None

def analyze_pdf(file_path: str) -> Tuple[Dict[str, Any], List[EvidenceRecord]]:
    raw_ref = str(uuid.uuid4())
    raw_meta = {"raw_ref": raw_ref}
    records = []
    
    if not fitz:
        records.append(_create_evidence("pdf_parse", EvidenceStatus.NOT_ANALYZABLE, {"reason": "PyMuPDF not installed"}, raw_ref))
        return raw_meta, records
        
    try:
        doc = fitz.open(file_path)
        meta = doc.metadata or {}
        raw_meta["metadata"] = meta
        
        with open(file_path, "rb") as f:
            content = f.read()
        eof_count = len(re.findall(b"%%EOF", content))
        raw_meta["revisions_eof_count"] = eof_count
        
        fonts_count = 0
        images_count = 0
        for page in doc:
            fonts_count += len(page.get_fonts())
            images_count += len(page.get_images())
            
        raw_meta["embedded_fonts"] = fonts_count
        raw_meta["embedded_images"] = images_count
        
        # 1. Producer/Creator
        producer = meta.get("producer", "")
        creator = meta.get("creator", "")
        records.append(_create_evidence("pdf_producer_creator", EvidenceStatus.OK, {
            "producer": producer if producer else "absent",
            "creator": creator if creator else "absent"
        }, raw_ref))
        
        # 2. Dates
        creation = meta.get("creationDate", "")
        mod = meta.get("modDate", "")
        
        date_obs = {
            "creation_date": creation if creation else "absent",
            "modification_date": mod if mod else "absent"
        }
        
        if creation and mod:
            c_dt = _parse_pdf_date(creation)
            m_dt = _parse_pdf_date(mod)
            if c_dt and m_dt:
                diff_seconds = (m_dt - c_dt).total_seconds()
                date_obs["modification_difference_seconds"] = diff_seconds
                if diff_seconds > 0:
                    date_obs["finding"] = f"modification date is {diff_seconds} seconds after creation date"
                elif diff_seconds < 0:
                    date_obs["finding"] = f"modification date is {abs(diff_seconds)} seconds before creation date"
                else:
                    date_obs["finding"] = "modification date matches creation date"
            else:
                date_obs["finding"] = "dates present but unparseable"
                
        records.append(_create_evidence("pdf_dates", EvidenceStatus.OK, date_obs, raw_ref))
        
        # 3. Revisions
        records.append(_create_evidence("pdf_revisions", EvidenceStatus.OK, {
            "eof_marker_count": eof_count,
            "finding": f"found {eof_count} %%EOF markers indicating revision/incremental-update count"
        }, raw_ref))
        
        # 4. Embedded contents
        records.append(_create_evidence("pdf_embedded_content", EvidenceStatus.OK, {
            "fonts_count": fonts_count,
            "images_count": images_count
        }, raw_ref))
        
    except Exception as e:
        records.append(_create_evidence("pdf_parse", EvidenceStatus.NOT_ANALYZABLE, {"reason": str(e)}, raw_ref))
        
    return raw_meta, records

def analyze_image(file_path: str) -> Tuple[Dict[str, Any], List[EvidenceRecord]]:
    raw_ref = str(uuid.uuid4())
    raw_meta = {"raw_ref": raw_ref}
    records = []
    
    if not Image:
        records.append(_create_evidence("image_parse", EvidenceStatus.NOT_ANALYZABLE, {"reason": "Pillow not installed"}, raw_ref))
        return raw_meta, records
        
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if exif:
                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, str(tag_id))
                    # Avoid serializing complex bytes objects
                    if isinstance(value, bytes):
                        exif_data[tag] = "<bytes>"
                    else:
                        exif_data[tag] = str(value)
                raw_meta["exif"] = exif_data
                
                records.append(_create_evidence("image_exif_presence", EvidenceStatus.OK, {
                    "exif_present": True,
                    "software": exif_data.get("Software", "absent"),
                    "datetime": exif_data.get("DateTime", "absent"),
                    "datetime_original": exif_data.get("DateTimeOriginal", "absent")
                }, raw_ref))
            else:
                raw_meta["exif"] = None
                records.append(_create_evidence("image_exif_presence", EvidenceStatus.OK, {
                    "exif_present": False,
                    "software": "absent",
                    "datetime": "absent",
                    "datetime_original": "absent"
                }, raw_ref))
                
    except Exception as e:
        records.append(_create_evidence("image_parse", EvidenceStatus.NOT_ANALYZABLE, {"reason": str(e)}, raw_ref))
        
    return raw_meta, records
