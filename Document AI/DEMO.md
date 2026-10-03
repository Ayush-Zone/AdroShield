# ForgeryLens: Demo & Documentation

## How to Run the Demo

ForgeryLens comes with a pipeline orchestrator and a UI-friendly demo hook. To run the pipeline and see the generated payload (which is formatted for frontend overlay consumption):

```powershell
# Set PYTHONPATH so the forgerylens package resolves
$env:PYTHONPATH="src"

# Execute the demo runner with a sample file
python demo_runner.py "tests\samples\invoice_1.png"
```

The runner will output a structured JSON payload containing document provenence, timestamp, and a list of `findings`. Each finding provides its methodology, a human-readable message, and optional bounding boxes (normalized 0.0 to 1.0) and raw ELA map URIs.

## How to Test

ForgeryLens includes a robust `pytest` suite simulating diverse document permutations, including edge cases and upstream engine failures (via mocks).

```powershell
$env:PYTHONPATH="src"
python -m pytest -q -rs
```

- **Mocks vs Real Engines:** Phases 3 (OCR) tests use `unittest.mock` for Tesseract so tests can pass cleanly on machines lacking the `tesseract.exe` binary. Conversely, Phase 9 (Forensics) tests run against real synthesized image arrays (via `PIL` / `numpy`) and real PDF parsing (`fitz` / `PyMuPDF`) to prove pixel/ELA and metadata math.

## Known Limitations

As designed in the `ARCHITECTURE.md` boundary, ForgeryLens focuses strictly on structural, arithmetical, and metadata-level anomalies.

1. **What Analyzers CANNOT Detect:**
   - **Identity/Deepfakes:** ForgeryLens does not perform face matching or deepfake manipulation detection. That remains the domain of `IdentityMatch` and `PixelWitness`.
   - **Hardware Forensics:** Camera noise profiling and strict EXIF GPS spoofing detection are owned by `ProofShot`, not ForgeryLens.
   - **Vector Image Manipulation:** Advanced manipulation of purely vector PDF elements (without rasterization artifacts or metadata footprints) may evade pixel-based Error Level Analysis.
   - **Non-JPEG Image History:** Error Level Analysis (ELA) inherently requires a baseline of lossy JPEG compression. Pure lossless PNGs or documents without JPEG compression history will return `NOT_ANALYZABLE` rather than fabricating a score.
2. **Skipped Phases:**
   - Phases 7 and 8 were functionally merged into the architecture's orchestration (Phase 10), as the "Findings/Investigator Evidence" and "Shared AnalysisResult" are handled natively by mapping `EvidenceRecord` instances inside the `EvidenceBundle` structure.
   - Real-world production integration into the broader `adroshield-ai` global risk engine has been deferred (out of scope for `Document AI/` isolation).
