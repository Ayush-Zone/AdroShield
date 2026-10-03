import sys
import argparse
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont
import fitz
import json
import hashlib
from pathlib import Path

from forgerylens.contracts.evidence import EvidenceBundle, EvidenceRecord
from forgerylens.contracts.storage import make_artifact_ref
from forgerylens.pipeline import STORAGE_ROOT

PDF_DPI = 150
BOX_COLOR = "red"
FOOTER_HEIGHT_PX = 40
CAPTION_TEXT_BOXES = "Red boxes mark regions referenced by evidence records. This is not a tampering verdict."
CAPTION_TEXT_EMPTY = "No evidence regions to display."

class SkippedRecord(BaseModel):
    evidence_id: str
    reason: str

class ManifestBox(BaseModel):
    label: str
    evidence_id: str
    evidence_type: str
    status: str
    normalized_box: Dict[str, float]
    pixel_box: Dict[str, int]

class OverlayManifest(BaseModel):
    boxes: List[ManifestBox] = []
    skipped: List[SkippedRecord] = []

class OverlayResult(BaseModel):
    artifact_refs: List[str] = Field(default_factory=list)
    skipped: List[SkippedRecord] = Field(default_factory=list)

def _get_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def should_draw_box(record: EvidenceRecord, include_all_located: bool) -> bool:
    if record.status.value == "not_analyzable" if hasattr(record.status, 'value') else record.status == "not_analyzable":
        return False
    if not record.location:
        return False
    if include_all_located:
        return True

    if record.type == "forensic_ela_region":
        return True
    if record.status.value == "ambiguous" if hasattr(record.status, 'value') else record.status == "ambiguous":
        return True
    if isinstance(record.observation, dict) and record.observation.get("result") == "mismatch":
        return True
    return False

def render_evidence_overlay(file_path: str, bundle: EvidenceBundle, include_all_located: bool = False) -> OverlayResult:
    source_sha256 = _get_sha256(file_path)

    pages: Dict[int, Image.Image] = {}
    is_pdf = file_path.lower().endswith(".pdf")

    if is_pdf:
        doc = fitz.open(file_path)
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=PDF_DPI)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages[i + 1] = img
    else:
        img = Image.open(file_path).convert("RGB")
        pages[1] = img

    manifest = OverlayManifest()
    boxes_by_page: Dict[int, List[Tuple[str, EvidenceRecord]]] = {p: [] for p in pages.keys()}

    for i, record in enumerate(bundle.evidence):
        if not should_draw_box(record, include_all_located):
            continue

        loc = record.location
        if not loc:
            continue

        if loc.page_number not in pages:
            manifest.skipped.append(SkippedRecord(evidence_id=record.id, reason=f"Page {loc.page_number} does not exist"))
            continue

        if not (0.0 <= loc.x <= 1.0 and 0.0 <= loc.y <= 1.0 and 0.0 <= loc.width <= 1.0 and 0.0 <= loc.height <= 1.0):
            manifest.skipped.append(SkippedRecord(evidence_id=record.id, reason="Coordinates out of [0, 1] bounds"))
            continue

        label = f"#{i}"
        boxes_by_page[loc.page_number].append((label, record))

    result_refs = []
    storage_dir = STORAGE_ROOT / source_sha256
    storage_dir.mkdir(parents=True, exist_ok=True)

    for page_num, img in pages.items():
        w, h = img.size

        new_img = Image.new("RGB", (w, h + FOOTER_HEIGHT_PX), color="white")
        new_img.paste(img, (0, 0))

        draw = ImageDraw.Draw(new_img)
        line_width = max(2, int(w * 0.002))

        has_boxes = False

        for label, record in boxes_by_page[page_num]:
            loc = record.location
            px_x = int(loc.x * w)
            px_y = int(loc.y * h)
            px_w = int(loc.width * w)
            px_h = int(loc.height * h)

            if px_x < 0 or px_y < 0 or px_w < 0 or px_h < 0 or px_x + px_w > w or px_y + px_h > h:
                manifest.skipped.append(SkippedRecord(evidence_id=record.id, reason="Pixel bounding box out of bounds"))
                continue

            has_boxes = True

            draw.rectangle([px_x, px_y, px_x + px_w, px_y + px_h], outline=BOX_COLOR, width=line_width)
            draw.text((px_x, max(0, px_y - 15)), label, fill=BOX_COLOR)

            manifest.boxes.append(ManifestBox(
                label=label,
                evidence_id=record.id,
                evidence_type=record.type,
                status=record.status.value if hasattr(record.status, 'value') else str(record.status),
                normalized_box={"x": loc.x, "y": loc.y, "width": loc.width, "height": loc.height},
                pixel_box={"x": px_x, "y": px_y, "width": px_w, "height": px_h}
            ))

        caption = CAPTION_TEXT_BOXES if has_boxes else CAPTION_TEXT_EMPTY
        draw.text((10, h + 10), caption, fill="black")

        artifact_name = f"overlay_p{page_num}.png"
        out_path = storage_dir / artifact_name
        new_img.save(out_path, format="PNG")

        ref = make_artifact_ref(source_sha256, artifact_name)
        result_refs.append(ref)

    manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
    manifest_path = storage_dir / "overlay_manifest.json"
    manifest_path.write_bytes(manifest_bytes)

    ref = make_artifact_ref(source_sha256, "overlay_manifest.json")
    result_refs.append(ref)

    return OverlayResult(artifact_refs=result_refs, skipped=manifest.skipped)
