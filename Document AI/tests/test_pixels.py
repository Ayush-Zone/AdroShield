import pytest
import os
import io
import cv2
import numpy as np
from PIL import Image

from forgerylens.forensics.pixels import (
    analyze_pixels, 
    MAX_REGIONS_EMITTED, 
    MIN_VARIANCE,
    MIN_PIXEL_COUNT,
    MIN_RESOLUTION
)
from forgerylens.contracts.evidence import EvidenceStatus
from tests.test_forensics import assert_neutral_observation

# --- Fixtures ---

@pytest.fixture
def unedited_jpeg(tmp_path):
    path = tmp_path / "clean.jpg"
    # Create a gradient image so it has high variance and looks natural-ish
    # Shape must be > MIN_RESOLUTION (e.g. 200x200)
    w, h = 200, 200
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            arr[y, x] = [x % 256, y % 256, (x+y) % 256]
            
    img = Image.fromarray(arr)
    img.save(path, format="JPEG", quality=95)
    return str(path)

@pytest.fixture
def edited_jpeg(tmp_path, unedited_jpeg):
    path = tmp_path / "edited.jpg"
    img = Image.open(unedited_jpeg).convert("RGB")
    arr = np.array(img)
    
    # Synthetically edit by pasting a solid black block (which changes JPEG 8x8 blocks)
    # in the middle of the image. This breaks compression consistency.
    edit_box = (50, 50, 100, 100) # y1, x1, y2, x2
    arr[50:100, 50:100] = [0, 0, 0]
    
    edited_img = Image.fromarray(arr)
    # Save at a slightly different quality to exacerbate ELA
    edited_img.save(path, format="JPEG", quality=85)
    return str(path)

@pytest.fixture
def png_image(tmp_path):
    path = tmp_path / "image.png"
    img = Image.new("RGB", (200, 200), color="blue")
    img.save(path, format="PNG")
    return str(path)

@pytest.fixture
def blank_image(tmp_path):
    path = tmp_path / "blank.jpg"
    img = Image.new("RGB", (200, 200), color="white")
    img.save(path, format="JPEG", quality=100)
    return str(path)

@pytest.fixture
def tiny_image(tmp_path):
    path = tmp_path / "tiny.jpg"
    img = Image.new("RGB", (10, 10), color="red")
    img.save(path, format="JPEG")
    return str(path)

# --- Tests ---

def test_png_not_analyzable(png_image):
    raw_map, records = analyze_pixels(png_image)
    for r in records:
        assert_neutral_observation(r)
    assert len(records) == 1
    ev = records[0]
    assert ev.status == EvidenceStatus.NOT_ANALYZABLE
    assert ev.observation["analyzability"] == "not_analyzable"
    assert "no JPEG compression history (PNG input)" in ev.observation["reasons"]
    assert raw_map == b""

def test_pdf_rasterized_not_analyzable(unedited_jpeg):
    # Pass a valid JPEG but set is_pdf_rasterized=True
    raw_map, records = analyze_pixels(unedited_jpeg, is_pdf_rasterized=True)
    for r in records:
        assert_neutral_observation(r)
    assert len(records) == 1
    assert records[0].status == EvidenceStatus.NOT_ANALYZABLE
    assert "no JPEG compression history (PDF input)" in records[0].observation["reasons"]

def test_blank_image(blank_image):
    raw_map, records = analyze_pixels(blank_image)
    for r in records:
        assert_neutral_observation(r)
    assert len(records) == 1
    assert records[0].status == EvidenceStatus.NOT_ANALYZABLE
    assert any("variance" in r and "blank" in r for r in records[0].observation["reasons"])

def test_tiny_image(tiny_image):
    raw_map, records = analyze_pixels(tiny_image)
    for r in records:
        assert_neutral_observation(r)
    assert len(records) == 1
    assert records[0].status == EvidenceStatus.NOT_ANALYZABLE
    assert any("resolution" in r for r in records[0].observation["reasons"])

def test_unedited_jpeg_clean(unedited_jpeg):
    raw_map, records = analyze_pixels(unedited_jpeg)
    for r in records:
        assert_neutral_observation(r)
    analyzability = records[0]
    assert analyzability.status == EvidenceStatus.OK
    assert analyzability.observation["analyzability"] == "analyzable"
    
    ela_records = records[1:]
    for r in ela_records:
        assert r.type == "forensic_ela_region"
        assert r.observation["confidence"] is None
        assert "weak indicator" in r.observation["limitations"]

def test_edited_jpeg(edited_jpeg):
    # We placed a block from x=50..100, y=50..100
    raw_map, records = analyze_pixels(edited_jpeg)
    for r in records:
        assert_neutral_observation(r)
    analyzability = records[0]
    assert analyzability.status == EvidenceStatus.OK
    
    ela_records = records[1:]
    assert len(ela_records) > 0
    
    # Verify at least one region overlaps with the edited box
    edit_x1, edit_y1 = 50, 50
    edit_x2, edit_y2 = 100, 100
    
    overlap_found = False
    for r in ela_records:
        box = r.observation["bbox_px"]
        # Check intersection
        bx1, by1 = box["x"], box["y"]
        bx2, by2 = bx1 + box["width"], by1 + box["height"]
        
        # Overlap condition
        if not (bx2 < edit_x1 or bx1 > edit_x2 or by2 < edit_y1 or by1 > edit_y2):
            overlap_found = True
            break
            
    assert overlap_found, "No ELA region overlapped the synthetically edited box"

def test_region_cap(unedited_jpeg):
    # Let's create an image that will produce many regions to test MAX_REGIONS_EMITTED
    img = Image.open(unedited_jpeg)
    arr = np.array(img)
    # Add high frequency noise to create many ELA edges
    noise = np.random.randint(0, 50, arr.shape, dtype=np.uint8)
    noisy_img = Image.fromarray(np.clip(arr + noise, 0, 255))
    noisy_img.save(unedited_jpeg, format="JPEG", quality=90)
    
    raw_map, records = analyze_pixels(unedited_jpeg)
    for r in records:
        assert_neutral_observation(r)
    ela_records = records[1:]
    assert len(ela_records) <= MAX_REGIONS_EMITTED
    
    if len(ela_records) == MAX_REGIONS_EMITTED:
        assert "MAX_REGIONS_EMITTED cap" in ela_records[-1].observation.get("note", "")

def test_same_input_twice_identical(unedited_jpeg):
    raw_map1, records1 = analyze_pixels(unedited_jpeg)
    raw_map2, records2 = analyze_pixels(unedited_jpeg)
    
    assert raw_map1 == raw_map2
    assert len(records1) == len(records2)
    # Compare bounding boxes
    for r1, r2 in zip(records1[1:], records2[1:]):
        assert r1.observation["bounding_box"] == r2.observation["bounding_box"]

def test_file_unchanged(edited_jpeg):
    with open(edited_jpeg, "rb") as f:
        before = f.read()
        
    analyze_pixels(edited_jpeg)
    
    with open(edited_jpeg, "rb") as f:
        after = f.read()
        
    assert before == after
