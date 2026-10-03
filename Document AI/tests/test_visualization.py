import os
import json
import uuid
import hashlib
from pathlib import Path
from decimal import Decimal
from PIL import Image, ImageDraw
import fitz
import subprocess
import pytest

from forgerylens.contracts.evidence import EvidenceBundle, EvidenceRecord, EvidenceStatus, Provenance, EvidenceLocation
from forgerylens.visualization.overlay import render_evidence_overlay, CAPTION_TEXT_EMPTY, CAPTION_TEXT_BOXES, BOX_COLOR, FOOTER_HEIGHT_PX, PDF_DPI
from forgerylens.contracts.storage import resolve_artifact_ref
from forgerylens.pipeline import STORAGE_ROOT

def _dummy_prov():
    return Provenance(source_file_sha256="dummy", tool_name="test", tool_version="1")

def _get_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def test_jpeg_edited_box_and_unmodified_pixels(tmp_path):
    # 1. Create a simple JPEG
    img_path = tmp_path / "test.jpg"
    img = Image.new("RGB", (100, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 20, 20], fill="black")
    img.save(img_path, format="JPEG", quality=90)

    orig_hash = _get_hash(img_path)

    # 2. Create bundle with a forensic_ela_region
    loc = EvidenceLocation(page_number=1, x=0.1, y=0.1, width=0.1, height=0.1)
    record = EvidenceRecord(
        id=str(uuid.uuid4()),
        type="forensic_ela_region",
        status=EvidenceStatus.OK,
        observation={"bounding_box": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}},
        location=loc,
        method="ela",
        provenance=_dummy_prov()
    )
    bundle = EvidenceBundle(document_provenance=_dummy_prov(), evidence=[record])

    # 3. Render
    res = render_evidence_overlay(str(img_path), bundle)

    # 4. Check outputs
    assert len(res.skipped) == 0
    assert len(res.artifact_refs) == 2 # 1 image, 1 manifest

    png_path = resolve_artifact_ref(res.artifact_refs[0], STORAGE_ROOT)
    assert png_path.exists()

    # Check pixels outside box
    out_img = Image.open(png_path).convert("RGB")
    assert out_img.size == (100, 100 + FOOTER_HEIGHT_PX)

    # Inside the box outline should be red
    # The bounding box is 10,10 to 20,20. The outline is drawn there.
    px = out_img.load()
    # At (10, 10) it should be red
    assert px[10, 10] == (255, 0, 0)

    # Outside the box, e.g. at 50,50, it should be the original color (white)
    assert px[50, 50] == (255, 255, 255)

    # Original file unchanged
    assert _get_hash(img_path) == orig_hash

    # Check manifest
    man_path = resolve_artifact_ref(res.artifact_refs[1], STORAGE_ROOT)
    man = json.loads(man_path.read_text())
    assert len(man["boxes"]) == 1
    assert man["boxes"][0]["evidence_id"] == record.id

    # No local paths in payload
    assert "C:\\" not in man_path.read_text()
    assert "/" not in man_path.read_text() or "artifact:" in man_path.read_text() # well, just check no absolute paths

def test_pdf_scaling_and_multipage(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    # Page 1
    page1 = doc.new_page(width=200, height=300)
    # Page 2
    page2 = doc.new_page(width=400, height=600)
    doc.save(pdf_path)

    loc1 = EvidenceLocation(page_number=1, x=0.5, y=0.5, width=0.1, height=0.1)
    record1 = EvidenceRecord(id=str(uuid.uuid4()), type="forensic_ela_region", status=EvidenceStatus.OK, observation={}, location=loc1, method="test", provenance=_dummy_prov())

    loc2 = EvidenceLocation(page_number=2, x=0.2, y=0.2, width=0.2, height=0.2)
    record2 = EvidenceRecord(id=str(uuid.uuid4()), type="consistency_check_foo", status=EvidenceStatus.OK, observation={"result": "mismatch"}, location=loc2, method="test", provenance=_dummy_prov())

    bundle = EvidenceBundle(document_provenance=_dummy_prov(), evidence=[record1, record2])

    res = render_evidence_overlay(str(pdf_path), bundle)

    # Should produce 2 PNGs + 1 manifest = 3 refs
    assert len(res.artifact_refs) == 3
    man_path = resolve_artifact_ref(res.artifact_refs[-1], STORAGE_ROOT)
    man = json.loads(man_path.read_text())
    assert len(man["boxes"]) == 2

    # Box 1 pixel coords check (DPI scaling)
    b1 = [b for b in man["boxes"] if b["evidence_id"] == record1.id][0]
    expected_w = 200 * (PDF_DPI / 72.0)
    expected_h = 300 * (PDF_DPI / 72.0)
    assert abs(b1["pixel_box"]["x"] - int(0.5 * expected_w)) <= 1

def test_out_of_range_skipped(tmp_path):
    img_path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100), color="white").save(img_path, format="JPEG")

    loc1 = EvidenceLocation(page_number=2, x=0.5, y=0.5, width=0.1, height=0.1) # wrong page
    r1 = EvidenceRecord(id="r1", type="forensic_ela_region", status=EvidenceStatus.OK, observation={}, location=loc1, method="test", provenance=_dummy_prov())

    loc2 = EvidenceLocation.model_construct(page_number=1, x=1.5, y=0.5, width=0.1, height=0.1) # out of range
    r2 = EvidenceRecord(id="r2", type="forensic_ela_region", status=EvidenceStatus.OK, observation={}, location=loc2, method="test", provenance=_dummy_prov())

    bundle = EvidenceBundle(document_provenance=_dummy_prov(), evidence=[r1, r2])
    res = render_evidence_overlay(str(img_path), bundle)

    assert len(res.skipped) == 2
    assert res.skipped[0].evidence_id == "r1"
    assert res.skipped[1].evidence_id == "r2"

def test_not_analyzable_never_boxed(tmp_path):
    img_path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100), color="white").save(img_path, format="JPEG")

    loc = EvidenceLocation(page_number=1, x=0.5, y=0.5, width=0.1, height=0.1)
    r1 = EvidenceRecord(id="r1", type="forensic_ela_region", status=EvidenceStatus.NOT_ANALYZABLE, observation={}, location=loc, method="test", provenance=_dummy_prov())
    r2 = EvidenceRecord(id="r2", type="consistency_check_foo", status=EvidenceStatus.OK, observation={"result": "exact"}, location=loc, method="test", provenance=_dummy_prov())

    bundle = EvidenceBundle(document_provenance=_dummy_prov(), evidence=[r1, r2])

    # With include_all_located=False, neither gets a box
    res1 = render_evidence_overlay(str(img_path), bundle)
    man1 = json.loads(resolve_artifact_ref(res1.artifact_refs[-1], STORAGE_ROOT).read_text())
    assert len(man1["boxes"]) == 0

    # With include_all_located=True, only r2 gets a box (r1 is not_analyzable)
    res2 = render_evidence_overlay(str(img_path), bundle, include_all_located=True)
    man2 = json.loads(resolve_artifact_ref(res2.artifact_refs[-1], STORAGE_ROOT).read_text())
    assert len(man2["boxes"]) == 1
    assert man2["boxes"][0]["evidence_id"] == "r2"

def test_no_evidence_caption(tmp_path):
    img_path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100), color="white").save(img_path, format="JPEG")

    bundle = EvidenceBundle(document_provenance=_dummy_prov(), evidence=[])
    res = render_evidence_overlay(str(img_path), bundle)

    png_path = resolve_artifact_ref(res.artifact_refs[0], STORAGE_ROOT)

    # The footer strip should exist
    out_img = Image.open(png_path).convert("RGB")
    assert out_img.size == (100, 100 + FOOTER_HEIGHT_PX)

    # Tesseract or just manual check: we assume the caption is there.
    # We can check that the footer is non-uniform (meaning text was drawn)
    footer = out_img.crop((0, 100, 100, 140))
    extrema = footer.getextrema()
    # At least one color channel should have variance (text is black, bg is white)
    assert any(vmin < vmax for vmin, vmax in extrema)

def test_cli_execution(tmp_path):
    img_path = tmp_path / "test_cli.jpg"
    img = Image.new("RGB", (200, 200), color="white")
    ImageDraw.Draw(img).text((10, 10), "Invoice", fill="black")
    img.save(img_path, format="JPEG")

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        ["python", "-m", "forgerylens.visualization", str(img_path)],
        cwd=".",
        env=env,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Overlay Artifacts Generated:" in result.stdout
    assert "overlay_manifest.json" in result.stdout
