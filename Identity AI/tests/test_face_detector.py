"""Tests for Identity AI face detection layer.

Tests triage logic:
- Exactly 1 face: status 'ok', face_count 1
- 0 faces: status 'inconclusive', indicator 'NO_FACE_DETECTED'
- >1 faces: status 'inconclusive', indicator 'MULTIPLE_FACES_DETECTED'
- Invalid/corrupt inputs: status 'error'
All fixtures use synthetic images or mocked detector responses without personal data.
"""

import sys
from pathlib import Path
from typing import List

import pytest
from PIL import Image

# Ensure Identity AI/src is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from face_detector import (
    BaseFaceDetector,
    BoundingBox,
    FaceDetectionResult,
    HaarCascadeFaceDetector,
    detect_faces,
)
from preprocessor import PreprocessingResult


class MockFaceDetector(BaseFaceDetector):
    """Deterministic mock detector to test triage states without real face images."""

    def __init__(self, mock_boxes: List[BoundingBox], raise_error: bool = False):
        self.mock_boxes = mock_boxes
        self.raise_error = raise_error

    def detect_raw(self, image: Image.Image) -> List[BoundingBox]:
        if self.raise_error:
            raise RuntimeError("Simulated detector internal failure.")
        return self.mock_boxes


def test_bounding_box_coordinates():
    """Verify BoundingBox calculations and boundary properties."""
    box = BoundingBox(x=10, y=20, width=50, height=80)

    assert box.x == 10
    assert box.y == 20
    assert box.width == 50
    assert box.height == 80
    assert box.xmin == 10
    assert box.ymin == 20
    assert box.xmax == 60
    assert box.ymax == 100
    assert box.to_tuple() == (10, 20, 50, 80)


def test_triage_exactly_one_face():
    """Verify exactly 1 face produces status 'ok' and face_count 1."""
    box = BoundingBox(x=30, y=40, width=100, height=120)
    detector = MockFaceDetector(mock_boxes=[box])
    synthetic_image = Image.new("RGB", (200, 200), color=(128, 128, 128))

    result = detector.detect_faces(synthetic_image)

    assert result.status == "ok"
    assert result.face_count == 1
    assert len(result.bounding_boxes) == 1
    assert result.bounding_boxes[0] == box
    assert result.indicator is None
    assert "exactly one" in result.message.lower()


def test_triage_zero_faces():
    """Verify 0 faces produces status 'inconclusive' and indicator 'NO_FACE_DETECTED'."""
    detector = MockFaceDetector(mock_boxes=[])
    synthetic_image = Image.new("RGB", (200, 200), color=(50, 50, 50))

    result = detector.detect_faces(synthetic_image)

    assert result.status == "inconclusive"
    assert result.face_count == 0
    assert result.bounding_boxes == []
    assert result.indicator == "NO_FACE_DETECTED"
    assert "no faces" in result.message.lower()


def test_triage_multiple_faces():
    """Verify multiple faces produces status 'inconclusive' and indicator 'MULTIPLE_FACES_DETECTED'."""
    box1 = BoundingBox(x=10, y=10, width=50, height=50)
    box2 = BoundingBox(x=80, y=80, width=60, height=60)
    detector = MockFaceDetector(mock_boxes=[box1, box2])
    synthetic_image = Image.new("RGB", (300, 300), color=(200, 200, 200))

    result = detector.detect_faces(synthetic_image)

    assert result.status == "inconclusive"
    assert result.face_count == 2
    assert len(result.bounding_boxes) == 2
    assert result.indicator == "MULTIPLE_FACES_DETECTED"
    assert "multiple faces" in result.message.lower()


def test_triage_unexpected_detector_error():
    """Verify unexpected detector failure produces status 'error'."""
    detector = MockFaceDetector(mock_boxes=[], raise_error=True)
    synthetic_image = Image.new("RGB", (100, 100))

    result = detector.detect_faces(synthetic_image)

    assert result.status == "error"
    assert result.face_count == 0
    assert result.indicator == "DETECTION_EXCEPTION"
    assert "unexpected error" in result.message.lower()


def test_triage_invalid_input_type():
    """Verify unsupported input type produces status 'error'."""
    detector = MockFaceDetector(mock_boxes=[])
    result = detector.detect_faces(12345)

    assert result.status == "error"
    assert result.face_count == 0
    assert result.indicator == "INVALID_INPUT_TYPE"
    assert "unsupported input type" in result.message.lower()


def test_triage_failed_preprocessing_result():
    """Verify failed PreprocessingResult input returns error status."""
    failed_prep = PreprocessingResult(
        status="error",
        image=None,
        original_mode=None,
        final_mode="",
        dimensions=None,
        orientation_applied=False,
        message="Corrupt file input",
    )
    detector = MockFaceDetector(mock_boxes=[])
    result = detector.detect_faces(failed_prep)

    assert result.status == "error"
    assert result.face_count == 0
    assert result.indicator == "PREPROCESSING_FAILED"


def test_triage_from_synthetic_file_path(tmp_path: Path):
    """Verify end-to-end execution passing a file path into detect_faces."""
    img_path = tmp_path / "blank_test.png"
    Image.new("RGB", (150, 150), color=(100, 100, 100)).save(img_path)

    box = BoundingBox(x=20, y=20, width=60, height=60)
    detector = MockFaceDetector(mock_boxes=[box])

    result = detect_faces(img_path, detector=detector)

    assert result.status == "ok"
    assert result.face_count == 1
    assert result.bounding_boxes[0].to_tuple() == (20, 20, 60, 60)


def test_triage_from_nonexistent_file(tmp_path: Path):
    """Verify nonexistent file returns status error safely."""
    missing_path = tmp_path / "missing.jpg"
    detector = MockFaceDetector(mock_boxes=[])

    result = detect_faces(missing_path, detector=detector)

    assert result.status == "error"
    assert result.indicator == "INPUT_PREPROCESSING_ERROR"


def test_haar_cascade_on_blank_image():
    """Verify actual HaarCascadeFaceDetector runs on synthetic image and finds 0 faces."""
    detector = HaarCascadeFaceDetector()
    blank_image = Image.new("RGB", (200, 200), color=(255, 255, 255))

    result = detector.detect_faces(blank_image)

    # A blank white rectangle should have 0 faces detected
    assert result.status == "inconclusive"
    assert result.face_count == 0
    assert result.indicator == "NO_FACE_DETECTED"
    assert result.bounding_boxes == []
