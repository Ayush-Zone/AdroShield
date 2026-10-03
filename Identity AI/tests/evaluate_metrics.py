import sys
import os
import math
from typing import List

# Setup path so we can import from Identity AI/src
identity_ai_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if identity_ai_path not in sys.path:
    sys.path.insert(0, identity_ai_path)

from src.similarity import compare_embeddings

def generate_mock_embedding(distance_target: float) -> tuple[List[float], List[float]]:
    """Creates a pair of mock 2D embeddings that evaluate to the exact target cosine distance."""
    # Using cos(theta) = 1 - distance
    cos_theta = 1.0 - distance_target
    if cos_theta > 1.0: cos_theta = 1.0
    if cos_theta < -1.0: cos_theta = -1.0
    sin_theta = math.sqrt(1 - cos_theta**2)
    return [1.0, 0.0], [cos_theta, sin_theta]

def run_evaluation():
    print("=== ADROSHIELD Identity AI: Evaluation Metrics ===")
    
    # 1. Simulate 50 "Genuine" pairs (distance <= 0.20)
    genuine_pairs = []
    for i in range(50):
        # Distances from 0.01 to 0.19
        dist = 0.01 + (i * 0.0036)
        genuine_pairs.append(generate_mock_embedding(dist))
        
    # 2. Simulate 50 "Imposter" pairs (distance > 0.40)
    imposter_pairs = []
    for i in range(50):
        # Distances from 0.45 to 0.94
        dist = 0.45 + (i * 0.01)
        imposter_pairs.append(generate_mock_embedding(dist))
        
    # Risk engine considers distance <= 0.20 as "Consistent" (Match)
    evaluation_threshold = 0.20
    
    false_rejects = 0
    true_accepts = 0
    
    false_accepts = 0
    true_rejects = 0
    
    print("Processing genuine pairs...")
    for emb1, emb2 in genuine_pairs:
        res = compare_embeddings(emb1, emb2, threshold=evaluation_threshold)
        if res.is_match:
            true_accepts += 1
        else:
            false_rejects += 1
            
    print("Processing imposter pairs...")
    for emb1, emb2 in imposter_pairs:
        res = compare_embeddings(emb1, emb2, threshold=evaluation_threshold)
        if res.is_match:
            false_accepts += 1
        else:
            true_rejects += 1
            
    # Calculate Metrics
    far = false_accepts / len(imposter_pairs) if imposter_pairs else 0.0
    frr = false_rejects / len(genuine_pairs) if genuine_pairs else 0.0
    
    print("\n--- Evaluation Report ---")
    print(f"Total Genuine Pairs:  {len(genuine_pairs)}")
    print(f"Total Imposter Pairs: {len(imposter_pairs)}")
    print("-------------------------")
    print(f"True Positives (Genuines Accepted):  {true_accepts}")
    print(f"False Negatives (Genuines Rejected): {false_rejects}")
    print(f"True Negatives (Imposters Rejected): {true_rejects}")
    print(f"False Positives (Imposters Accepted): {false_accepts}")
    print("-------------------------")
    print(f"False Accept Rate (FAR): {far * 100:.2f}%")
    print(f"False Reject Rate (FRR): {frr * 100:.2f}%")
    print("==================================================")

if __name__ == '__main__':
    run_evaluation()
