import ast
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# --- IMPORT AUDIT TEST ---

def get_imports(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def test_requirements_cover_imports():
    stdlib = {'os', 'sys', 'ast', 'pathlib', 'typing', 'json', 're', 'uuid', 'unittest', 'datetime', 'enum', 'collections', 'warnings', 'logging', 'argparse', 'subprocess', 'hashlib', 'io', 'decimal', 'shutil'}
    local_modules = {'forgerylens', 'classifier', 'consistency', 'currency', 'dates', 'extractor', 'metadata', 'models', 'normalizer', 'pixels', 'text', 'validator', 'tests'}

    alias_map = {
        'cv2': 'opencv-python',
        'PIL': 'pillow',
        'fitz': 'pymupdf'
    }

    optional_allowlist = {'paddleocr'}

    all_imports = set()
    repo_root = Path(__file__).parent.parent

    for folder in ['src', 'tests']:
        folder_path = repo_root / folder
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.py'):
                    all_imports.update(get_imports(Path(root) / file))

    third_party = {imp for imp in all_imports if imp not in stdlib and not any(imp.startswith(loc) for loc in local_modules)}

    # Read requirements.txt
    req_file = repo_root / 'requirements.txt'
    with open(req_file, 'r', encoding='utf-8') as f:
        declared = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # strip version constraints
                pkg = line.split('>')[0].split('<')[0].split('=')[0].lower()
                declared.append(pkg)

    declared_set = set(declared)

    for imp in third_party:
        if imp in optional_allowlist:
            continue

        pkg_name = alias_map.get(imp, imp).lower()
        assert pkg_name in declared_set, f"Import '{imp}' (package '{pkg_name}') is used but not declared in requirements.txt"

# --- PIPELINE TESTS FOR COVERAGE MAP GAPS ---

from forgerylens.pipeline import run_pipeline
from forgerylens.contracts.enums import IngestionStatus, DocumentFormat
from forgerylens.contracts.evidence import EvidenceStatus, Provenance, EvidenceRecord
import uuid
from forgerylens.contracts.structured import DocumentType

@patch("forgerylens.pipeline.ingest_document")
@patch("forgerylens.pipeline.extract_document_text")
@patch("forgerylens.pipeline.analyze_pdf")
@patch("forgerylens.pipeline.analyze_pixels")
def test_pipeline_ocr_failure_sibling_analyzers_run(
    mock_pixels, mock_meta_pdf, mock_ocr, mock_ingest, tmp_path
):
    """
    OCR failure test: force the OCR engine to raise and assert not_analyzable evidence,
    with sibling analyzers still running.
    """
    dummy_jpeg = tmp_path / "test.jpg"
    dummy_jpeg.write_bytes(b"dummy")

    mock_ingest.return_value = MagicMock(status=IngestionStatus.VALID, format=DocumentFormat.JPEG, page_count=1)

    # OCR fails
    mock_ocr.side_effect = Exception("OCR Engine crashed")

    prov = Provenance(source_file_sha256="test", tool_name="test", tool_version="1.0", parameters={})
    mock_pixels.return_value = (b"dummy_map", [EvidenceRecord(id=str(uuid.uuid4()), type="forensic_ela_region", status=EvidenceStatus.OK, observation={}, method="test", provenance=prov)])

    bundle = run_pipeline(str(dummy_jpeg))

    types = {e.type: e.status for e in bundle.evidence}

    # OCR failed -> not_analyzable
    assert types.get("text_extraction") == EvidenceStatus.NOT_ANALYZABLE

    # Sibling analyzers still ran (pixels runs for JPEG)
    assert mock_pixels.called
    assert types.get("forensic_ela_region") == EvidenceStatus.OK


@patch("forgerylens.pipeline.ingest_document")
@patch("forgerylens.pipeline.extract_document_text")
@patch("forgerylens.pipeline.classify_document")
@patch("forgerylens.pipeline.analyze_pdf")
@patch("forgerylens.pipeline.analyze_pixels")
def test_pipeline_line_items_validation(
    mock_pixels, mock_meta_pdf, mock_classify, mock_ocr, mock_ingest, tmp_path
):
    """
    Test line items reaching validation.
    We don't mock parse_document or normalize_document or run_all_consistency_checks.
    Instead we provide fake OCR text that parses into line items.
    """
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"dummy")

    mock_ingest.return_value = MagicMock(status=IngestionStatus.VALID, format=DocumentFormat.PDF, page_count=1)

    from forgerylens.contracts.ocr import OCRWord
    page_mock = MagicMock(full_text="Invoice Number: 1234\nDate: 2026-10-01\nDescription Qty Rate Amount\nWidget A 1 10.00 10.00\nSubtotal: $10.00\nTotal: $10.00")
    page_mock.page_number = 1
    page_mock.extraction_method.value = "mocked"
    page_mock.words = [
        OCRWord(text="Invoice Number: 1234", x=0.1, y=0.1, width=0.5, height=0.05, confidence=1.0),
        OCRWord(text="Date: 2026-10-01", x=0.1, y=0.15, width=0.5, height=0.05, confidence=1.0),

        # Header row to trigger in_table
        OCRWord(text="Description Qty Rate Amount", x=0.1, y=0.2, width=0.8, height=0.05, confidence=1.0),

        # Line item
        OCRWord(text="Widget A", x=0.1, y=0.25, width=0.2, height=0.05, confidence=1.0),
        OCRWord(text="1", x=0.4, y=0.25, width=0.05, height=0.05, confidence=1.0),
        OCRWord(text="10.00", x=0.5, y=0.25, width=0.1, height=0.05, confidence=1.0),
        OCRWord(text="10.00", x=0.7, y=0.25, width=0.1, height=0.05, confidence=1.0),

        OCRWord(text="Subtotal: $10.00", x=0.1, y=0.35, width=0.5, height=0.05, confidence=1.0),
        OCRWord(text="Total: $10.00", x=0.1, y=0.45, width=0.5, height=0.05, confidence=1.0)
    ]
    mock_ocr_result = MagicMock(status=IngestionStatus.VALID, pages=[page_mock])
    mock_ocr_result.document_id = "test_doc_id"
    mock_ocr.return_value = mock_ocr_result

    prov = Provenance(source_file_sha256="test", tool_name="test", tool_version="1.0", parameters={})
    mock_classify.return_value = EvidenceRecord(id="cls", type="classification", status=EvidenceStatus.OK, observation={"document_type": DocumentType.INVOICE.value}, method="test", provenance=prov)

    mock_meta_pdf.return_value = (None, [])
    mock_pixels.return_value = (None, [])

    bundle = run_pipeline(str(dummy_pdf))

    types = {e.type: e.status for e in bundle.evidence}
    print([e.observation for e in bundle.evidence if e.type == "pack_orchestration"])

    # Line items should be extracted, normalized, and reach consistency validation.
    # Validation will produce consistency checks for subtotal vs total and line items vs subtotal.
    assert "consistency_check_line_items_vs_subtotal" in types

    print([e.observation for e in bundle.evidence if e.type == "consistency_check_line_items_vs_subtotal"])

    assert types["consistency_check_line_items_vs_subtotal"] == EvidenceStatus.OK
