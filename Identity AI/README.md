# Identity AI Module

## Overview
Identity AI is an evidence-producing subsystem for the **ADROSHIELD** claim fraud detection platform. Its future objective is to assess facial consistency between an official ID-document image and an applicant selfie.

> **Important Boundary:** Identity AI produces investigative evidence signals only. It does **not** make final fraud decisions, approve/reject claims, or calculate overall risk scores (which are strictly handled upstream by the central Risk Engine).

---

## Phase 1 Scope: Validation & Preprocessing
Phase 1 focuses solely on robust, safe, and deterministic image input validation and color/orientation normalization.

### Supported Image Formats
- **JPEG / JPG**
- **PNG**

All other formats (e.g., GIF, BMP, WebP, PDF, TIFF) are rejected during validation.

---

## Architecture & Pipeline

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
   └── Packaging clean PIL Image for future models
       │
       ▼
[Future Phases]
3. Face Detection (Phase 2)
4. Face Embedding & Comparison (Phase 3)
5. Structured Identity Result
```

---

## Result States

The module outputs structured results using three standardized states:

| Status | Meaning | Examples |
| :--- | :--- | :--- |
| `ok` | Image passed all structural and visual decoding checks | Valid JPEG/PNG readable into RGB |
| `inconclusive` | File parsed but image properties are non-standard or degenerate | Zero or negative dimensions |
| `error` | Technical or file input failure | Missing file, corrupt stream, unsupported extension, 0 bytes |

> **Distinction:** A validation `error` reflects a technical input problem (e.g. corrupted file), **not** an identity mismatch.

---

## What Is Intentionally NOT Implemented Yet
To maintain disciplined development and avoid premature model coupling:
- ❌ **No Face Detection:** MTCNN / RetinaFace / Haar cascades are not run.
- ❌ **No Face Recognition / Embeddings:** DeepFace, FaceNet512, PyTorch, and TensorFlow are intentionally not installed or imported.
- ❌ **No Face Matching or Similarity Calculations:** Cosine distance and threshold matching are deferred to Phase 3.
- ❌ **No Identity Verification or Fraud Decisions:** No legal identity verification or risk scoring.
- ❌ **No Backend/API Integration:** Backend orchestrator integration occurs after the shared contract is finalized.

---

## Current Limitations
- **Format Support:** Only single-image JPEG and PNG files are supported in this phase (multi-page PDFs or TIFFs are not processed).
- **Face Presence:** An image will pass Phase 1 validation as long as it is a valid JPEG/PNG, even if no human face is present (face detection is scheduled for Phase 2).
- **Shared Contract:** The output schema is internal to `Identity AI` and will be aligned with the core integration owner prior to service integration.

---

## Testing

Tests are written using `pytest` and use programmatically generated synthetic images without any private personal data or customer identity documents.

### Running Tests

To run the test suite from the repository root:

```bash
pytest "Identity AI/tests" -v
```
