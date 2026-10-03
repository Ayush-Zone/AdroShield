# BUG LEDGER

| ID | Status | Planned Phase | Evidence / Notes |
|---|---|---|---|
| FL-01 | CONFIRMED | P2 | `pipeline.py:146` bypasses extraction/normalization layers |
| FL-02 | CONFIRMED | P2 | `packs/invoice/extractor.py:135` stubs `line_items=[]` |
| FL-03 | CONFIRMED | P3 | `pipeline.py:201` calls pixels on rasterized PDFs |
| FL-04 | CONFIRMED | P3 | `pixels.py:174` emits unnormalized px bounds |
| FL-05 | CONFIRMED | P3 | `metadata.py:98` emits conclusions instead of observations |
| FL-06 | CONFIRMED | P3 | `metadata.py:111` emits conclusion for EOF markers |
| FL-07 | CONFIRMED | P3 | `metadata.py:126` discards raw_meta, no storage used |
| FL-08 | CONFIRMED | P5 | `benchmark_report.md` uses paddleocr but not in requirements |
| FL-09 | CONFIRMED | P3 | `pixels.py:50` reads image quality directly as signal |
| FL-10 | CONFIRMED | P3 | ELA algorithm yields high false positives on text |
| FL-11 | CONFIRMED | P3 | `metadata.py:156` returns OK for absent EXIF |
| FL-12 | CONFIRMED | P3 | `metadata.py:98` flags regular mod dates as finding |
| FL-13 | CONFIRMED | P3 | `pipeline.py` unused json and raw_meta |
| FL-14 | CONFIRMED | P4 | `demo_hook.py:57` fabricates suspicious_score |
| FL-15 | CONFIRMED | P4 | `demo_hook.py:60` flattens evidence into generic message |
| FL-16 | CLOSED | P1 | `ARCHITECTURE.md` stale language and outputs removed |
| FL-17 | CLOSED | P1 | `BUG_LEDGER.md` created |
| FL-18 | CONFIRMED | P2 | `pipeline.py` contains old phase labels in comments |
| FL-19 | CONFIRMED | P2 | `pipeline.py` silently uses `datetime.now()` |
| FL-20 | CONFIRMED | P2 | Currency normalization yields float, consistency uses Decimal |
| AF-1 | CONFIRMED | P2 | OCR fallback lacks pipeline observation record |
| AF-2 | CONFIRMED | P2 | Text extraction record lacks word count/source info |
| AF-3 | CONFIRMED | P2 | Classification fails if PyMuPDF yields no text |
