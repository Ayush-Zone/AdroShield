"""Identity Matcher layer for ADROSHIELD Identity AI.

Orchestrates the full pipeline: Validation -> Preprocessing -> Detection -> Embedding -> Similarity.
"""
from dataclasses import dataclass
from typing import Optional

from .validator import validate_image, ValidationStatus
from .preprocessor import preprocess_image
from .face_detector import detect_faces, BaseFaceDetector
from .embedder import BaseFaceEmbedder
from .similarity import compare_embeddings

@dataclass(frozen=True)
class MatchResult:
    """End-to-end result for an identity match attempt."""
    status: str
    is_match: bool = False
    distance: float = 0.0
    indicator: Optional[str] = None
    message: str = ""

class IdentityMatcher:
    """Orchestrates the evidence-producing matching pipeline."""
    
    def __init__(
        self,
        embedder: BaseFaceEmbedder,
        detector: Optional[BaseFaceDetector] = None,
        threshold: float = 0.4
    ):
        self.embedder = embedder
        self.detector = detector
        self.threshold = threshold

    def _process_single_image(self, image_path: str, image_role: str):
        # 1. Validation
        val_result = validate_image(image_path)
        if val_result.status != ValidationStatus.OK:
            return {"status": "error", "indicator": "VALIDATION_FAILED", "message": f"{image_role} validation failed: {val_result.message}"}
            
        # 2. Preprocessing
        prep_result = preprocess_image(val_result)
        if prep_result.status != "ok":
            return {"status": "error", "indicator": "PREPROCESSING_FAILED", "message": f"{image_role} preprocessing failed."}
            
        # 3. Detection
        det_result = detect_faces(prep_result, self.detector)
        if det_result.status != "ok":
            return {"status": "error", "indicator": det_result.indicator or "DETECTION_FAILED", "message": f"{image_role} face detection issue: {det_result.message}"}
            
        # 4. Embedding
        emb_result = self.embedder.get_embedding(prep_result.image, det_result)
        if emb_result.status != "ok":
            return {"status": "error", "indicator": emb_result.indicator or "EMBEDDING_FAILED", "message": f"{image_role} embedding issue: {emb_result.message}"}
            
        return {"status": "ok", "embedding": emb_result.embedding}

    def match_identity(self, document_path: str, selfie_path: str) -> MatchResult:
        """Execute the full identity matching pipeline."""
        # Process Document
        doc_res = self._process_single_image(document_path, "Document")
        if doc_res["status"] != "ok":
            return MatchResult(status="error", indicator=doc_res["indicator"], message=doc_res["message"])
            
        # Process Selfie
        selfie_res = self._process_single_image(selfie_path, "Selfie")
        if selfie_res["status"] != "ok":
            return MatchResult(status="error", indicator=selfie_res["indicator"], message=selfie_res["message"])
            
        # 5. Similarity
        sim_result = compare_embeddings(doc_res["embedding"], selfie_res["embedding"], threshold=self.threshold)
        if sim_result.status != "ok":
            return MatchResult(status="error", indicator=sim_result.indicator, message=sim_result.message)
            
        return MatchResult(
            status="ok",
            is_match=sim_result.is_match,
            distance=sim_result.distance,
            message="Identity match computed successfully."
        )
