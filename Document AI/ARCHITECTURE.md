# ForgeryLens (Document AI) — Architecture & Foundation Plan

**Document Version:** 1.0.0  
**Phase:** Phase 0 (Reconnaissance & Foundation Planning)  
**Branch:** `anurag_forgery`  
**Target Module:** `Document AI/`  
**Status:** Approved for Foundation Planning; Implementation on Hold  

---

## 1. Repository Observations

A comprehensive inspection of the new repository (`c:\Users\kumar\Desktop\AdroShield`) revealed the following state:

- **Git & Branching:**
  - Active Branch: `anurag_forgery` (tracking `origin/anurag_forgery`).
  - Working tree is clean.
  - Active branches identified across team: `main`, `anurag`, `anurag_forgery`, `nitin`, `nitin_identity`, `prashant`.
  - Strict protocol: Never commit directly to `main`; all document intelligence work must remain committed to `anurag_forgery`.
- **Directory Layout:**
  - `Document AI/`: Currently contains only a placeholder file (`New Text Document.txt`).
  - `Identity AI/`: Contains placeholder file (`New Text Document.txt`).
  - `Image AI/`: Contains placeholder file (`New Text Document.txt`).
  - `models/`: Contains placeholder file (`New Text Document.txt`).
  - `README.md`: Minimal project header (`# AdroShield`).
- **Configuration & Dependencies:**
  - The new repository does not yet contain a root `pyproject.toml`, `requirements.txt`, or global test runner configuration.
  - The local Python environment is Python 3.10.11 with core packages available (`pydantic` 2.12.5, `pillow` 11.2.1, `pytest` 8.3.3, `torch` 2.7.1, `httpx` 0.27.2). Specific PDF/OCR packages (`pymupdf`, `pytesseract`) are not yet installed in this environment.
- **Contracts & Shared Code:**
  - No shared schemas, models, or orchestrator services currently exist in `main` or `anurag_forgery`.
  - Remote branch `origin/prashant` contains early model setup scripts (`download_model.py`, `inspect_model.py`, `.gitignore`), but no shared API contracts have been merged to `main`.

---

## 2. Existing Relevant Architecture (Reference Repository Review)

Review of the reference repository (`PRRASHANT/adroshield-ai`) highlighted key patterns and lessons:

### Architectural Patterns
- **Modular Monolith:** Analyzers (`PixelWitness`, `ForgeryLens`, `IdentityMatch`, `ProofShot`) run within a common backend while maintaining distinct domain boundaries.
- **Canonical Envelope (`AnalysisResult`):** All analyzers report outcomes through a unified schema:
  - `module: str`
  - `status: Status` (`ok`, `inconclusive`, `error`, `not_provided`)
  - `risk: Optional[int]` (0–100 review priority score; `None` on error/not_provided)
  - `model_score: Optional[float]` (raw model output for audit)
  - `findings: List[Finding]` (granular discrepancy list)
  - `data: Dict[str, Any]` (structured extracted fields)
  - `error_message: Optional[str]`
- **Granular Findings (`Finding`):**
  - Machine-readable `code` (e.g., `LINE_ITEM_MISMATCH`, `INVOICE_TOTAL_MISMATCH`, `GRAND_TOTAL_MISMATCH`)
  - Human-readable `message`
  - `severity: Severity` (`info`, `low`, `medium`, `high`)
  - `evidence_id: str`
  - `region: Optional[Region]` (normalized bounding boxes `x, y, width, height` in `[0, 1]`)
  - `details: Dict[str, Any]`

### Reference Implementation of ForgeryLens
- Located under `backend/app/document/`:
  - `extractor.py`: Uses PyMuPDF (`fitz`) for native text extraction; falls back to Tesseract OCR for scanned PDFs or images.
  - `checks.py`: Regex-based extraction of invoice fields (invoice number, date, line items, subtotals, taxes, discounts, grand totals) and arithmetic verification.
  - `document_service.py`: Orchestrates extraction -> field parsing -> arithmetic checks -> risk score computation.

### Gaps & Improvements Needed for ADROSHIELD
1. **Directory Isolation:** Reference code was tightly coupled to FastAPI backend internals. In this new repo, all ForgeryLens logic must reside in `Document AI/` as a modular, reusable package.
2. **Pluggable OCR & Graceful Fallback:** Tesseract was a hard external dependency in the reference. If Tesseract was missing or unconfigured, OCR failed with warnings. A robust abstraction is required that supports native PDF text, OCR engines, or mock extraction during offline testing.
3. **Extraction Robustness:** Reference regex parsing was brittle (single regex per line format). We need a structured layout/field parser supporting multiple invoice styles and receipt formats.
4. **Forensic & Metadata Anomaly Detection:** The reference repo only performed arithmetic checks. ForgeryLens must also inspect document metadata (producer software, creation/modification discrepancies), font inconsistencies, and suspicious layout overlays.
5. **Auditable Language & Neutral Tone:** In strict compliance with ADROSHIELD guidelines, findings must never label documents as "fraudulent". They must describe objective observations: *"discrepancy detected"*, *"inconsistent amount"*, *"missing field"*, *"formatting anomaly"*, *"metadata anomaly"*, *"unable to verify"*, or *"requires review"*.

---

## 3. ForgeryLens Responsibility Boundary

A strict boundary ensures ForgeryLens operates autonomously without encroaching on sibling modules or premature global adjudication.

### ✅ OWNED BY FORGERYLENS
- **Document Ingestion & Validation:**
  - Handling PDFs (native and scanned) and document images (`.png`, `.jpeg`, `.jpg`, `.tiff`).
  - File integrity checks, format validation, and corrupted file handling.
- **Text & Coordinate Extraction (OCR):**
  - Dual-mode extraction: high-fidelity native PDF text/word extraction + OCR for rasterized pages.
  - Bounding box extraction with coordinate normalization to `[0, 1]`.
- **Structured Information Extraction:**
  - Parsing document header metadata (invoice number, issue date, due date).
  - Extracting vendor and counterparty entities.
  - Parsing tabular line items (description, quantity, unit price, line amount).
  - Extracting financial totals (subtotal, taxes, fees, discounts, grand total).
- **Normalization:**
  - Currency normalization (handling INR `₹`, USD `$`, commas, decimal separators).
  - Date normalization to standard ISO-8601 strings.
  - Field key normalization across disparate document layouts.
- **Validation & Consistency Analysis:**
  - Mathematical integrity: $\text{Quantity} \times \text{Unit Price} \approx \text{Line Amount}$.
  - Subtotal integrity: $\sum \text{Line Amounts} \approx \text{Subtotal}$.
  - Grand total integrity: $\text{Subtotal} + \text{Taxes} + \text{Fees} - \text{Discounts} \approx \text{Grand Total}$.
  - Logical temporal integrity (e.g., invoice date vs. repair/claim timeline).
- **Document Forensic & Anomaly Indicators:**
  - PDF metadata anomalies (creator tool alterations, mismatched creation/modification dates).
  - Formatting anomalies (mixed font families in numeric fields, misaligned totals).
  - Obfuscation or tampering signals (layer mismatches, hidden text).
- **Investigator Evidence & Findings Generation:**
  - Producing structured, investigator-readable findings with severity ratings (`info`, `low`, `medium`, `high`).
  - Attaching exact bounding box regions to findings.
  - Formulating neutral, objective evidence descriptions.
- **Canonical Envelope Packaging:**
  - Outputting an `AnalysisResult`-compliant dictionary or Pydantic model for consumption by downstream orchestrators.

---

### ❌ NOT OWNED BY FORGERYLENS
- **Image Deepfake Detection:** Manipulated accident photographs or scene tampering (owned by `PixelWitness` / `Image AI`).
- **Face & Identity Verification:** Matching claimant selfies against government IDs (owned by `IdentityMatch` / `Identity AI`).
- **Camera / Hardware Forensics:** Camera sensor noise, EXIF validation of accident photos (owned by `ProofShot`).
- **Cross-Evidence Correlation:** Comparing repair estimate line items against damage visible in accident photos (owned by Evidence Correlation layer).
- **Global Claim Risk Aggregation:** Calculating global claim risk across all 4 modules (owned by Risk Engine).
- **Final Fraud Adjudication:** ForgeryLens never decides whether a claim is accepted or rejected; that is strictly the domain of human investigators assisted by the dashboard.
- **Frontend Presentation:** React dashboard UI rendering (owned by UI layer).

---

## 4. Dependencies on Other Modules

```
                    ┌─────────────────────────┐
                    │   Document (PDF/Image)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     =========================
                     │      FORGERYLENS      │
                     │     (Document AI)     │
                     =========================
                                 │
                                 │ Returns AnalysisResult
                                 ▼
                    ┌─────────────────────────┐
                    │   Quality Assessment    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Signal Normalization   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Evidence Correlation   │  <-- (Correlates with PixelWitness,
                    └────────────┬────────────┘       IdentityMatch, ProofShot)
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       Risk Engine       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Investigator Dashboard  │
                    └─────────────────────────┘
```

### Inbound Dependencies
- ForgeryLens requires:
  - Access to raw document files (file path or byte stream).
  - An evidence identifier (`evidence_id`) to correlate findings.
  - Optional document classification hint (e.g., `repair_invoice`, `medical_bill`, `estimate`).

### Outbound Deliverables
- ForgeryLens emits:
  - An `AnalysisResult` contract containing:
    - Module status (`ok`, `inconclusive`, `error`, `not_provided`)
    - Document review-priority score (heuristic 0–100, reflecting document-level discrepancy weight)
    - Normalized structured document fields (`InvoiceData`)
    - Granular `Finding` objects with localized bounding boxes and objective discrepancy messages.

---

## 5. Proposed `Document AI/` Internal Structure

To ensure modularity and clean progression through subsequent phases, the module will be structured as follows:

```
Document AI/
├── ARCHITECTURE.md              # Architectural specification & roadmap (this document)
├── pyproject.toml / requirements.txt # Module-level dependencies
├── src/
│   └── forgerylens/
│       ├── __init__.py          # Public API export (analyze_document, schemas)
│       ├── contracts/           # Pydantic schemas (AnalysisResult, Finding, InvoiceData)
│       │   ├── __init__.py
│       │   ├── enums.py         # Status, Severity, FindingCode
│       │   ├── models.py        # AnalysisResult, Finding, Region
│       │   └── document.py     # InvoiceData, LineItem, DocumentMetadata
│       ├── ingestion/           # File handling, validation, MIME detection
│       │   ├── __init__.py
│       │   └── reader.py
│       ├── ocr/                 # Dual extraction: native PDF + OCR
│       │   ├── __init__.py
│       │   ├── native.py        # PDF text & word extraction with bounding boxes
│       │   ├── ocr_engine.py    # Image/scanned OCR interface
│       │   └── normalizer.py   # Bounding box coordinate normalization [0, 1]
│       ├── extraction/          # Structured field extraction
│       │   ├── __init__.py
│       │   ├── parser.py        # Template/regex invoice parsing
│       │   └── patterns.py      # Field regex patterns & entity extractors
│       ├── normalization/       # Data sanitation
│       │   ├── __init__.py
│       │   ├── currency.py      # Multi-currency parsing (INR, USD) to Decimal
│       │   └── dates.py         # Date parsing to ISO-8601
│       ├── validation/          # Consistency & integrity engine
│       │   ├── __init__.py
│       │   ├── arithmetic.py    # Quantity*Rate, Subtotal sum, Grand total checks
│       │   └── logical.py       # Date chronology, missing mandatory fields
│       ├── forensics/           # Document anomaly detection
│       │   ├── __init__.py
│       │   └── metadata.py      # PDF metadata, producer inspection, anomaly signals
│       └── service.py           # Main ForgeryLens service orchestrator
└── tests/
    ├── __init__.py
    ├── conftest.py              # Test fixtures (sample invoices, mock pages)
    ├── test_ingestion.py        # PDF/image loading tests
    ├── test_ocr.py              # Text extraction tests
    ├── test_extraction.py       # Field extraction tests
    ├── test_normalization.py    # Currency & date normalization tests
    ├── test_validation.py       # Arithmetic & consistency tests
    ├── test_forensics.py        # Metadata anomaly tests
    └── test_service.py          # End-to-end ForgeryLens pipeline tests
```

---

## 6. Proposed Phased Implementation Plan

| Phase | Title | Scope & Objectives | Key Deliverables |
|---|---|---|---|
| **Phase 0** | **Reconnaissance & Architecture** | Repository inspection, reference review, boundaries definition, architecture blueprint. | `Document AI/ARCHITECTURE.md` |
| **Phase 1** | **Foundation & Contracts** | Establish module skeleton, package config, core Pydantic contracts (`AnalysisResult`, `Finding`, `Region`, `InvoiceData`), and testing harness. | `Document AI/src/forgerylens/contracts/`, test runner setup |
| **Phase 2** | **Document Ingestion** | Support reading PDF and image formats (`png`, `jpg`, `tiff`), MIME type detection, file existence & corruption safety. | `ingestion/reader.py`, `tests/test_ingestion.py` |
| **Phase 3** | **OCR & Text Extraction** | Implement PyMuPDF native extraction + pluggable OCR engine (with graceful fallback if Tesseract is not installed) + coordinate normalizer. | `ocr/native.py`, `ocr/ocr_engine.py`, `tests/test_ocr.py` |
| **Phase 4** | **Structured Document Extraction** | Extract invoice number, dates, vendor details, tabular line items, and totals from raw text and token coordinates. | `extraction/parser.py`, `tests/test_extraction.py` |
| **Phase 5** | **Normalization Layer** | Convert diverse currency formats (e.g., `₹12,500.00`, `$1,200`) to `Decimal`, convert varied dates to ISO-8601, clean line items. | `normalization/currency.py`, `dates.py`, unit tests |
| **Phase 6** | **Validation & Consistency Engine** | Arithmetic verification ($\text{Qty} \times \text{Rate}$, line items sum, tax calculations, negative amounts, discrepancy delta calculation). | `validation/arithmetic.py`, `tests/test_validation.py` |
| **Phase 7** | **Document Anomaly & Forensics** | Check PDF metadata inconsistencies, creator software flags, modified dates preceding creation dates, font/format anomalies. | `forensics/metadata.py`, `tests/test_forensics.py` |
| **Phase 8** | **Findings & Investigator Evidence** | Map detected discrepancies into standardized `Finding` objects with localized bounding boxes and neutral evidence terminology. | Findings mapper, evidence generator |
| **Phase 9** | **Shared `AnalysisResult` Integration** | Assemble the top-level `AnalysisResult` envelope, calculate document review-priority score, handle inconclusive/error states. | `service.py`, integration tests |
| **Phase 10** | **Hardening & Edge-Case Testing** | Extensive testing on corrupted PDFs, zero-byte files, multi-page invoices, missing fields, extreme numbers, and non-standard layouts. | Full test suite, test documentation |

---

## 7. Decisions That Require Approval Before Phase 1

1. **OCR Engine Selection & System Dependencies:**
   - *Option A:* Use PyMuPDF (`fitz`) for native text + PyTesseract for scanned documents (requires local Tesseract binary installation on developer/server systems).
   - *Option B:* Dual strategy: PyMuPDF for native PDF text + lightweight pure-Python fallback (or mock/fallback mechanism) when Tesseract binary is not present on the host system, ensuring tests pass in all CI/local environments.
   - *Recommendation:* Option B for maximum portability and developer resilience.

2. **Schema Alignment Across Modules:**
   - Should ForgeryLens define its own internal contracts (`AnalysisResult`, `Finding`) that adhere to the reference standard, or will a central repository-level `shared/` or `contracts/` directory be established by the team lead?
   - *Recommendation:* Define canonical Pydantic models in `Document AI/src/forgerylens/contracts/` designed to be drop-in compatible with or easily relocated to a shared contracts module once the team harmonizes.

3. **Document Scope & Domain:**
   - The primary document types in motor and property claims are repair invoices, damage estimates, and parts bills. Are there additional document classes (e.g., medical claims, identity cards) expected to be parsed by ForgeryLens, or is IdentityMatch strictly handling identity cards?
   - *Recommendation:* ForgeryLens focuses on financial and repair documents (invoices, bills, estimates); `IdentityMatch` continues to own government identity documents.

---

## 8. Open Questions & Uncertainties

1. **Shared Orchestration:** How will the top-level FastAPI / orchestrator invoke ForgeryLens? (Direct Python module import vs. microservice HTTP/gRPC endpoint).
2. **Third-Party Model Weights:** Will ForgeryLens use lightweight rule-based/regex parsers or integrate pre-trained vision-language models (e.g., LayoutLM or Donut) for document parsing in later phases?
3. **Multi-Currency Support:** Does ADROSHIELD prioritize Indian Rupee (`INR` / `₹`) invoices, international (`USD`, `EUR`, `GBP`), or all?

---

*Phase 0 complete. No implementation code has been added. Awaiting approval to proceed to Phase 1.*
