"""Similarity calculation layer for Identity AI.

Compares two facial embeddings using distance metrics.
"""
from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass(frozen=True)
class SimilarityResult:
    """Structured result of similarity calculation."""
    status: str
    distance: float = 0.0
    threshold: float = 0.0
    is_match: bool = False
    metric: str = "cosine"
    message: str = ""
    indicator: str = ""

def calculate_cosine_distance(emb1: List[float], emb2: List[float]) -> float:
    """Calculate the cosine distance between two embedding vectors.
    
    Args:
        emb1: First embedding vector.
        emb2: Second embedding vector.
        
    Returns:
        Cosine distance (0.0 means identical, 2.0 means completely opposite).
    """
    v1 = np.array(emb1)
    v2 = np.array(emb2)
    
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        raise ValueError("Cannot calculate cosine distance of zero-vector.")
        
    cosine_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return float(1.0 - cosine_sim)

def compare_embeddings(
    embedding1: List[float], 
    embedding2: List[float], 
    threshold: float = 0.4,
    metric: str = "cosine"
) -> SimilarityResult:
    """Compare two facial embeddings to determine identity consistency.
    
    Args:
        embedding1: Document face embedding.
        embedding2: Selfie face embedding.
        threshold: Distance threshold (below which it's a match).
        metric: Distance metric to use ('cosine' is default).
        
    Returns:
        SimilarityResult indicating match status.
    """
    if not embedding1 or not embedding2:
        return SimilarityResult(
            status="error",
            indicator="INVALID_EMBEDDING",
            message="One or both embeddings are empty."
        )
        
    if len(embedding1) != len(embedding2):
        return SimilarityResult(
            status="error",
            indicator="DIMENSION_MISMATCH",
            message=f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}"
        )
        
    try:
        if metric == "cosine":
            distance = calculate_cosine_distance(embedding1, embedding2)
        else:
            return SimilarityResult(
                status="error",
                indicator="UNSUPPORTED_METRIC",
                message=f"Unsupported metric: {metric}"
            )
            
        is_match = distance <= threshold
        
        return SimilarityResult(
            status="ok",
            distance=distance,
            threshold=threshold,
            is_match=is_match,
            metric=metric,
            message="Comparison successful."
        )
    except Exception as exc:
        return SimilarityResult(
            status="error",
            indicator="CALCULATION_ERROR",
            message=f"Error calculating similarity: {exc}"
        )
