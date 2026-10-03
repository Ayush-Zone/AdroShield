import pytest
import os
import fitz
from PIL import Image
from forgerylens.forensics.metadata import analyze_pdf, analyze_image
from forgerylens.contracts.evidence import EvidenceStatus

@pytest.fixture
def clean_pdf(tmp_path):
    path = tmp_path / "clean.pdf"
    doc = fitz.open()
    doc.new_page()
    # No metadata set
    doc.save(path)
    doc.close()
    return str(path)

@pytest.fixture
def edited_pdf(tmp_path):
    path = tmp_path / "edited.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.set_metadata({
        "producer": "TestProducer",
        "creator": "TestCreator",
        "creationDate": "D:20261001120000",
        "modDate": "D:20261003120000"
    })
    doc.save(path)
    doc.close()
    
    # "Edit" the PDF by incremental save
    doc = fitz.open(path)
    doc.set_metadata({"modDate": "D:20261004120000"})
    doc.save(str(path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    return str(path)

@pytest.fixture
def no_exif_image(tmp_path):
    path = tmp_path / "no_exif.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(path)
    return str(path)

@pytest.fixture
def exif_image(tmp_path):
    path = tmp_path / "exif.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    exif = img.getexif()
    exif[305] = "TestSoftware" # Software tag
    exif[306] = "2026:10:03 12:00:00" # DateTime tag
    img.save(path, exif=exif)
    return str(path)

def test_pdf_no_metadata(clean_pdf):
    raw_meta, records = analyze_pdf(clean_pdf)
    
    prod_creator = next(r for r in records if r.type == "forensic_pdf_producer_creator")
    assert prod_creator.observation["producer"] == "absent"
    assert prod_creator.observation["creator"] == "absent"
    
    dates = next(r for r in records if r.type == "forensic_pdf_dates")
    assert dates.observation["creation_date"] == "absent"
    assert dates.observation["modification_date"] == "absent"
    
    # 1 %%EOF from the initial save
    revs = next(r for r in records if r.type == "forensic_pdf_revisions")
    assert revs.observation["eof_marker_count"] == 1

def test_pdf_edited_metadata(edited_pdf):
    raw_meta, records = analyze_pdf(edited_pdf)
    
    dates = next(r for r in records if r.type == "forensic_pdf_dates")
    assert "modification_difference_seconds" in dates.observation
    assert dates.observation["modification_difference_seconds"] > 0
    assert "after creation date" in dates.observation["finding"]
    
    # Initial save + incremental save = 2 %%EOF markers
    revs = next(r for r in records if r.type == "forensic_pdf_revisions")
    assert revs.observation["eof_marker_count"] == 2

def test_image_no_exif(no_exif_image):
    raw_meta, records = analyze_image(no_exif_image)
    
    pres = next(r for r in records if r.type == "forensic_image_exif_presence")
    assert pres.observation["exif_present"] is False
    assert pres.observation["software"] == "absent"

def test_image_with_exif(exif_image):
    raw_meta, records = analyze_image(exif_image)
    
    pres = next(r for r in records if r.type == "forensic_image_exif_presence")
    assert pres.observation["exif_present"] is True
    assert pres.observation["software"] == "TestSoftware"
    assert pres.observation["datetime"] == "2026:10:03 12:00:00"

def test_raw_dump_byte_identical(clean_pdf):
    # Verify we aren't altering the file on disk during extraction
    with open(clean_pdf, "rb") as f:
        before = f.read()
        
    analyze_pdf(clean_pdf)
    
    with open(clean_pdf, "rb") as f:
        after = f.read()
        
    assert before == after
