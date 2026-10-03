# Identity AI Module

## Overview
Identity AI is an evidence-producing subsystem for the **ADROSHIELD** claim fraud detection platform. Its objective is to assess facial consistency between an official ID-document image and an applicant selfie.

> **Important Boundary:** Identity AI produces investigative evidence signals only. It does **not** make final fraud decisions, approve/reject claims, or calculate overall risk scores (which are strictly handled upstream by the central Risk Engine).

---

## Pipeline Architecture

```text
Input (ID / Selfie)
       │
       ▼
1. Validation (Phase 1)
   ├── File existence & regular file check
   ├── Supported extension check (.jpg, .jpeg, .png)
   ├── Non-zero byte size check
   ├── Format integrity & decodability check
   └── Safe error handling (no unhandled exceptions)
       │
       ▼
2. Preprocessing (Phase 1)
   ├── EXIF orientation transpose (auto-correct mobile selfies/photos)
   ├── Normalization to 3-channel RGB
   ├── Neutral background compositing for transparency (RGBA/P)
   └── Packaging clean PIL Image for downstream detection
       │
       ▼
3. Face Detection & Triage (Phase 2)
   ├── Abstract BaseFaceDetector interface (pluggable engines)
   ├── Lightweight Haar Cascade implementation (OpenCV headless)
   ├── Bounding box extraction (x, y, w, h)
   └── Triage state evaluation (1 face vs 0 vs multiple)
       │
       ▼
[Deferred to Phase 3]
4. Face Embedding & Similarity Comparison (Phase 3)
5. Structured Identity Result
```

---

## Phase 2: Face Detection & Triage Logic

Phase 2 introduces a modular face detection layer with strict triage rules:

| Condition | Status | Indicator | Face Count | Meaning & Next Action |
| :--- | :--- | :--- | :--- | :--- |
| **Exactly 1 face** | `ok` | `None` | `1` | Single clear face isolated; eligible for Phase 3 embedding. |
| **0 faces detected** | `inconclusive` | `NO_FACE_DETECTED` | `0` | No face found in document/selfie; flagged for manual review. |
| **Multiple faces (>1)** | `inconclusive` | `MULTIPLE_FACES_DETECTED` | `>1` | Group photo or background faces; cannot disambiguate claimant. |
| **Corrupt / Invalid input** | `error` | `*ERROR*` | `0` | Technical input failure (e.g. unreadable bytes, bad input type). |

### Modular Architecture
- **`BaseFaceDetector`**: Abstract base class defining `detect_raw(image)` and `detect_faces(input_image)`. Enables seamless swapping with future detection engines (e.g., MediaPipe, RetinaFace, MTCNN) without altering the triage or downstream contracts.
- **`HaarCascadeFaceDetector`**: Lightweight, CPU-based default implementation using OpenCV's standard frontal face cascade (`haarcascade_frontalface_default.xml`).
- **`BoundingBox`**: Standardized bounding box dataclass with `x`, `y`, `width`, `height`, and boundary properties (`xmin`, `ymin`, `xmax`, `ymax`).

---

## What Is Intentionally NOT Implemented Yet
To maintain strict development discipline:
- ❌ **No Face Embeddings / Recognition Models:** DeepFace, FaceNet512, PyTorch, and TensorFlow are intentionally deferred to Phase 3.
- ❌ **No Similarity or Distance Calculations:** Cosine distance and threshold matching will be introduced in Phase 3.
- ❌ **No Identity Verification or Fraud Decisions:** No legal identity verification or risk scoring.
- ❌ **No Backend/API Integration:** Backend orchestrator integration occurs after core contracts are finalized.

---

## Current Limitations
- **Format Support:** Limited to single-image JPEG/JPG and PNG files.
- **Occlusion & Pose:** Highly turned profiles or partial occlusions may register as 0 faces with Haar cascades; pluggable architecture allows upgrading the detector in future iterations.

---

## Testing

Tests are written using `pytest` and use programmatically generated synthetic images and mock detectors without any real or sensitive customer identity documents.

### Running Tests

To run the complete test suite from the repository root:

```bash
pytest "Identity AI/tests" -v
```
