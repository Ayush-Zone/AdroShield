"""Face embedding layer for Identity AI.

Extracts facial embeddings from an image with a detected face.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional
import numpy as np
from PIL import Image

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

try:
    from .face_detector import FaceDetectionResult, BoundingBox
except ImportError:
    from face_detector import FaceDetectionResult, BoundingBox

@dataclass(frozen=True)
class FaceEmbeddingResult:
    """Structured result returned by the face embedding layer."""
    status: str
    embedding: Optional[List[float]] = None
    indicator: Optional[str] = None
    message: str = ""


class BaseFaceEmbedder(ABC):
    """Abstract base class defining the face embedding interface."""

    @abstractmethod
    def get_embedding_raw(self, image: Image.Image, bounding_box: BoundingBox) -> List[float]:
        """Extract embeddings from an RGB PIL Image and BoundingBox.
        
        Args:
            image: Clean 3-channel RGB PIL Image.
            bounding_box: BoundingBox of the face in the image.
            
        Returns:
            List of floats representing the face embedding.
        """
        raise NotImplementedError

    def get_embedding(
        self, 
        image: Image.Image, 
        detection_result: FaceDetectionResult
    ) -> FaceEmbeddingResult:
        """Execute face embedding using standard ADROSHIELD rules.
        
        Args:
            image: Clean RGB PIL Image.
            detection_result: FaceDetectionResult from the face detector.
            
        Returns:
            FaceEmbeddingResult containing the vector embedding.
        """
        if detection_result.status != "ok" or not detection_result.bounding_boxes:
            return FaceEmbeddingResult(
                status="error",
                indicator="INVALID_DETECTION",
                message="Cannot extract embedding: Face detection status is not ok or no boxes found."
            )
            
        try:
            # We assume exactly 1 face for 'ok' status based on triage rules
            target_box = detection_result.bounding_boxes[0]
            raw_embedding = self.get_embedding_raw(image, target_box)
            return FaceEmbeddingResult(
                status="ok",
                embedding=raw_embedding,
                message="Embedding extracted successfully."
            )
        except Exception as exc:
            return FaceEmbeddingResult(
                status="error",
                indicator="EMBEDDING_FAILED",
                message=f"Failed to extract embedding: {exc}"
            )


class DeepFaceEmbedder(BaseFaceEmbedder):
    """Embedder using the DeepFace library."""
    
    def __init__(self, model_name: str = "Facenet512") -> None:
        if not DEEPFACE_AVAILABLE:
            raise ImportError("DeepFace is required for DeepFaceEmbedder. Install with 'pip install deepface'.")
        self.model_name = model_name

    def get_embedding_raw(self, image: Image.Image, bounding_box: BoundingBox) -> List[float]:
        # Crop to bounding box provided by our detector
        face_img = image.crop((
            bounding_box.xmin, 
            bounding_box.ymin, 
            bounding_box.xmax, 
            bounding_box.ymax
        ))
        
        # Convert to NumPy array
        face_array = np.array(face_img)
        
        # DeepFace extraction, skipping its internal detection
        results = DeepFace.represent(
            img_path=face_array,
            model_name=self.model_name,
            enforce_detection=False,
            detector_backend="skip"
        )
        
        if not results or "embedding" not in results[0]:
            raise ValueError("DeepFace did not return a valid embedding.")
            
        return results[0]["embedding"]
