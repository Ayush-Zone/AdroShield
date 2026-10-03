"""Tests for the face embedding layer."""
import pytest
from PIL import Image
from src.embedder import BaseFaceEmbedder, DeepFaceEmbedder, FaceEmbeddingResult
from src.face_detector import FaceDetectionResult, BoundingBox

class MockFaceEmbedder(BaseFaceEmbedder):
    """A lightweight mock embedder for testing."""
    def get_embedding_raw(self, image, bounding_box):
        return [0.1, 0.2, 0.3, 0.4]

def test_mock_embedder_success():
    embedder = MockFaceEmbedder()
    img = Image.new("RGB", (100, 100))
    detection = FaceDetectionResult(
        status="ok", 
        face_count=1, 
        bounding_boxes=[BoundingBox(10, 10, 50, 50)]
    )
    result = embedder.get_embedding(img, detection)
    assert result.status == "ok"
    assert result.embedding == [0.1, 0.2, 0.3, 0.4]

def test_embedder_invalid_detection_status():
    embedder = MockFaceEmbedder()
    img = Image.new("RGB", (100, 100))
    detection = FaceDetectionResult(
        status="error", 
        face_count=0, 
        bounding_boxes=[]
    )
    result = embedder.get_embedding(img, detection)
    assert result.status == "error"
    assert result.indicator == "INVALID_DETECTION"

def test_embedder_exception_handling():
    class ExceptionEmbedder(BaseFaceEmbedder):
        def get_embedding_raw(self, image, bounding_box):
            raise ValueError("Simulated embedding failure")
            
    embedder = ExceptionEmbedder()
    img = Image.new("RGB", (100, 100))
    detection = FaceDetectionResult(
        status="ok", 
        face_count=1, 
        bounding_boxes=[BoundingBox(10, 10, 50, 50)]
    )
    result = embedder.get_embedding(img, detection)
    assert result.status == "error"
    assert result.indicator == "EMBEDDING_FAILED"
    assert "Simulated embedding failure" in result.message
