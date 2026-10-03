"""Identity AI module for ADROSHIELD.

Provides image validation, preprocessing, and face detection routines
for ID documents and selfie images as part of the identity verification pipeline.
"""

from .validator import ImageValidationResult, ValidationStatus, validate_image
from .preprocessor import PreprocessingResult, preprocess_image
from .face_detector import (
    BaseFaceDetector,
    BoundingBox,
    FaceDetectionResult,
    HaarCascadeFaceDetector,
    detect_faces,
)
from .embedder import (
    BaseFaceEmbedder,
    DeepFaceEmbedder,
    FaceEmbeddingResult,
)
from .similarity import SimilarityResult, compare_embeddings
from .matcher import MatchResult, IdentityMatcher

__all__ = [
    "ImageValidationResult",
    "ValidationStatus",
    "validate_image",
    "PreprocessingResult",
    "preprocess_image",
    "BoundingBox",
    "FaceDetectionResult",
    "BaseFaceDetector",
    "HaarCascadeFaceDetector",
    "detect_faces",
    "BaseFaceEmbedder",
    "DeepFaceEmbedder",
    "FaceEmbeddingResult",
    "SimilarityResult",
    "compare_embeddings",
    "MatchResult",
    "IdentityMatcher",
]
