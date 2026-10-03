"""Identity AI module for ADROSHIELD.

Provides image validation and preprocessing routines for ID documents
and selfie images as part of the identity verification pipeline.
"""

from .validator import ImageValidationResult, ValidationStatus, validate_image
from .preprocessor import PreprocessingResult, preprocess_image

__all__ = [
    "ImageValidationResult",
    "ValidationStatus",
    "validate_image",
    "PreprocessingResult",
    "preprocess_image",
]
