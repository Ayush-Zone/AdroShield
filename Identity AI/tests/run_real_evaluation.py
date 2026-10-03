import sys
import os
import numpy as np

# Setup path so we can import from Identity AI/src
identity_ai_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if identity_ai_path not in sys.path:
    sys.path.insert(0, identity_ai_path)

from src.matcher import IdentityMatcher
from src.embedder import DeepFaceEmbedder
from src.face_detector import BaseFaceDetector, FaceDetectionResult, BoundingBox
from deepface import DeepFace



class AdvancedFaceDetector(BaseFaceDetector):
    """Uses RetinaFace to ignore background noise and detect only real faces."""
    def detect_raw(self, image) -> list[BoundingBox]:
        try:
            img_array = np.array(image)
            # retinaface is highly accurate for high-res images and ID documents
            faces = DeepFace.extract_faces(img_path=img_array, detector_backend="retinaface", enforce_detection=False)
            
            # DeepFace returns a list of dictionaries. Filter out low-confidence ghost detections.
            valid_faces = [f for f in faces if f.get("confidence", 1.0) > 0.80]
            
            boxes = []
            for face in valid_faces:
                area = face["facial_area"]
                boxes.append(BoundingBox(x=area["x"], y=area["y"], width=area["w"], height=area["h"]))
            return boxes
        except Exception as e:
            print(f"RetinaFace detection error: {e}")
            return []

def run_real_evaluation():
    print("=== ADROSHIELD Identity AI: Real Image Evaluation ===")
    
    # Initialize the pipeline with the upgraded detector
    embedder = DeepFaceEmbedder(model_name="Facenet512")
    detector = AdvancedFaceDetector()
    matcher = IdentityMatcher(embedder=embedder, detector=detector, threshold=0.40)

    # File paths
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    obama_id = os.path.join(data_dir, "obama_id.jpg")
    obama_selfie = os.path.join(data_dir, "obama_selfie.jpg")
    jordan_selfie = os.path.join(data_dir, "jordan_selfie.jpg")

    print("\n[TEST 1] Genuine Match: Obama ID vs Obama Selfie")
    res1 = matcher.match_identity(obama_id, obama_selfie)
    print(f"Status: {res1.status}")
    if res1.status == "ok":
        print(f"Distance: {res1.distance:.4f} | Result: {'Consistent' if res1.is_match else 'Inconsistent'}")
    else:
        print(f"Error: {res1.indicator} - {res1.message}")

    print("\n[TEST 2] Imposter Match: Obama ID vs Michael Jordan Selfie")
    res2 = matcher.match_identity(obama_id, jordan_selfie)
    print(f"Status: {res2.status}")
    if res2.status == "ok":
        print(f"Distance: {res2.distance:.4f} | Result: {'Consistent' if res2.is_match else 'Inconsistent'}")
    else:
        print(f"Error: {res2.indicator} - {res2.message}")

if __name__ == '__main__':
    run_real_evaluation()
