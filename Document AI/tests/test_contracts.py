import pytest
from pathlib import Path
from forgerylens.contracts.spatial import normalize_bbox
from forgerylens.contracts.storage import make_artifact_ref, resolve_artifact_ref
from forgerylens.contracts.evidence import EvidenceLocation

def test_normalize_bbox_valid():
    assert normalize_bbox(50, 50, 100, 100, 200, 200) == (0.25, 0.25, 0.5, 0.5)

def test_normalize_bbox_edge():
    assert normalize_bbox(0, 0, 200, 200, 200, 200) == (0.0, 0.0, 1.0, 1.0)
    assert normalize_bbox(200, 200, 0, 0, 200, 200) == (1.0, 1.0, 0.0, 0.0)

def test_normalize_bbox_out_of_range():
    with pytest.raises(ValueError):
        normalize_bbox(-1, 0, 10, 10, 100, 100)
    with pytest.raises(ValueError):
        normalize_bbox(0, 0, 110, 10, 100, 100)

def test_normalize_bbox_zero_size():
    with pytest.raises(ValueError):
        normalize_bbox(0, 0, 10, 10, 0, 100)
    with pytest.raises(ValueError):
        normalize_bbox(0, 0, 10, 10, 100, -5)

def test_make_artifact_ref_valid():
    sha = "a" * 64
    assert make_artifact_ref(sha, "ela_map.png") == f"artifact:{sha}/ela_map.png"

def test_resolve_artifact_ref():
    storage_root = Path("/tmp/storage")
    sha = "a" * 64

    # Valid
    assert resolve_artifact_ref(f"artifact:{sha}/ela_map.png", storage_root) == (storage_root / sha / "ela_map.png").resolve()

    # Bad sha length
    with pytest.raises(ValueError):
        resolve_artifact_ref("artifact:abc/ela_map.png", storage_root)

    # Traversal ..
    with pytest.raises(ValueError):
        resolve_artifact_ref(f"artifact:{sha}/../ela_map.png", storage_root)

    # Traversal nested directory a/b
    with pytest.raises(ValueError):
        resolve_artifact_ref(f"artifact:{sha}/nested/ela_map.png", storage_root)

    # Traversal backslash
    with pytest.raises(ValueError):
        resolve_artifact_ref(f"artifact:{sha}/nested\\ela_map.png", storage_root)

    # Absolute path
    with pytest.raises(ValueError):
        resolve_artifact_ref(f"artifact:{sha}//etc/passwd", storage_root)

    # Empty name
    with pytest.raises(ValueError):
        resolve_artifact_ref(f"artifact:{sha}/", storage_root)

def test_evidence_location_enforces_bounds():
    # Valid
    EvidenceLocation(page_number=1, x=0.0, y=0.5, width=1.0, height=0.2)

    # Invalid
    with pytest.raises(ValueError):
        EvidenceLocation(page_number=1, x=-0.1, y=0.5, width=1.0, height=0.2)
    with pytest.raises(ValueError):
        EvidenceLocation(page_number=1, x=0.0, y=1.5, width=1.0, height=0.2)
    with pytest.raises(ValueError):
        EvidenceLocation(page_number=1, x=0.0, y=0.5, width=1.1, height=0.2)
