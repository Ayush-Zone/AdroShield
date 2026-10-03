# ForgeryLens (Document AI) — Architecture

**Document Version:** 2.0.0  
**Branch:** `anurag_forgery`  
**Target Module:** `Document AI/`  
**Status:** Active Implementation  

---

## 1. Purpose
Verified against code on 2026-10-04.
ForgeryLens is a rule-based document forensics library that ingests a single PDF or image file and emits a flat list of evidence records. Each record describes one objective observation (text extracted, field parsed, arithmetic checked, metadata inspected, pixel pattern measured). ForgeryLens never renders a verdict, score, or "fraud" label — it produces evidence for a human investigator or a downstream correlation engine.

## 2. Core Architectural Principle
Verified against code on 2026-10-04.
Strict separation of observation from conclusion. The library must not hallucinate missing data, silently correct ambiguities, or emit risk scores. All measurements must be traceable to raw bytes or normalized pixel regions.

## 3. High-Level ADROSHIELD Architecture
Verified against code on 2026-10-04.
ADROSHIELD operates via modular analyzers (ForgeryLens, PixelWitness, IdentityMatch). These feed a central correlation engine and risk engine. ForgeryLens is strictly a supplier of facts to the orchestrator. ForgeryLens does not make the global fraud decision.

---

## 4. Definitions

- **observation/evidence**: a measured fact.
- **finding**: a display grouping that references evidence IDs.
- **risk signal**: produced outside ForgeryLens.
- **global risk decision**: ADROSHIELD only.

## 5. Target Execution Flow
1. raw document
2. ingestion/validation
3. OCR or native text
4. classification
5. document-specific pack
6. structured fields with source regions
7. normalization
8. deterministic validation/consistency
9. forensic indicators
10. canonical EvidenceBundle
11. ADROSHIELD orchestrator

---

## 6. Output Schema and Result Mapping

EvidenceRecord and EvidenceBundle are the **canonical ForgeryLens output**. 

| Result Concept | Status | File Location |
|---|---|---|
| `EvidenceRecord` / `EvidenceBundle` | canonical | `src/forgerylens/contracts/evidence.py` |
| `OCRResult` | internal intermediate (not exposed) | `src/forgerylens/contracts/ocr.py` |
| `StructuredInvoice` | internal intermediate (not exposed) | `src/forgerylens/contracts/structured.py` |
| `FieldEvidence` | internal intermediate (not exposed) | `src/forgerylens/contracts/structured.py` |
| `ExtractedInvoicePack` | internal intermediate (not exposed) | `src/forgerylens/packs/invoice/models.py` |
| `ValidationResult` | deprecated | `src/forgerylens/contracts/validation.py` |

## 7. Contracts & Policies

### 7.1 Neutral-Wording Policy
Observations state what was measured; no tampering or fraud verdicts; absence or normal variation is not suspicious by itself.

### 7.2 Normalized Coordinate Contract
Locations are specified by page index plus x, y, width, height in [0,1] relative to the page/image, with the origin at the top-left. There is no silent clamping; if coordinates fall outside [0,1], they are invalid. The original pixel box and image size are kept in the observation.

### 7.3 Artifact Reference Contract
`raw_ref` is a logical ID of the form `artifact:<source_sha256>/<artifact_name>`. It is never a filesystem path or URL, and is resolved only through the resolver.

---

## 8. Single Entry Point

```python
from forgerylens.pipeline import run_pipeline
from forgerylens.contracts.evidence import EvidenceBundle

def run_pipeline(file_path: str) -> EvidenceBundle:
    pass
```
