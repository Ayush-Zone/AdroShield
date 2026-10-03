# BUG LEDGER

| ID | Status | Planned Phase | Evidence / Notes |
|---|---|---|---|
| FL-01 | ALREADY_FIXED | P2 | `pipeline.py:146` bypasses extraction/normalization layers |
| FL-02 | CLOSED | P2 | `packs/invoice/extractor.py:135` stubs `line_items=[]` |
| FL-03 | CLOSED | P3 | `pipeline.py:201` calls pixels on rasterized PDFs |
| FL-04 | CLOSED | P3 | `pixels.py:174` emits unnormalized px bounds |
| FL-05 | CLOSED | P3 | `metadata.py:98` emits conclusions instead of observations |
| FL-06 | CLOSED | P3 | `metadata.py:111` emits conclusion for EOF markers |
| FL-07 | CLOSED | P3 | `metadata.py:126` discards raw_meta, no storage used |
| FL-08 | CLOSED | P5 | `benchmark_report.md` uses paddleocr but not in requirements |
| FL-09 | CLOSED | P3 | `pixels.py:50` reads image quality directly as signal |
| FL-10 | CLOSED | P3 | ELA algorithm yields high false positives on text |
| FL-11 | CLOSED | P3 | `metadata.py:156` returns OK for absent EXIF |
| FL-12 | CLOSED | P3 | `metadata.py:98` flags regular mod dates as finding |
| FL-13 | CLOSED | P3 | `pipeline.py` unused json and raw_meta |
| FL-14 | CLOSED | P4 | `demo_hook.py:57` fabricates suspicious_score |
| FL-15 | CLOSED | P4 | `demo_hook.py:60` flattens evidence into generic message |
| FL-16 | CLOSED | P1 | `ARCHITECTURE.md` stale language and outputs removed |
| FL-17 | CLOSED | P1 | `BUG_LEDGER.md` created |
| FL-18 | ALREADY_FIXED | P2 | `pipeline.py` contains old phase labels in comments |
| FL-19 | ALREADY_FIXED | P2 | `pipeline.py` silently uses `datetime.now()` |
| FL-20 | ALREADY_FIXED | P2 | Currency normalization yields float, consistency uses Decimal |
| AF-1 | ALREADY_FIXED | P2 | OCR fallback lacks pipeline observation record |
| AF-2 | ALREADY_FIXED | P2 | Text extraction record lacks word count/source info |
| AF-3 | ALREADY_FIXED | P2 | Classification fails if PyMuPDF yields no text |
