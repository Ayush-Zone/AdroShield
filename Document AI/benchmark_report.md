# HISTORICAL / UNVERIFIED: OCR Engine Benchmark Report

> **Note**: The numbers below were produced with PaddleOCR. PaddleOCR is an optional dependency and is not declared in `requirements.txt`. Therefore, the results cannot be reproduced from the declared base environment as of today's date.
> To reproduce these results, first install PaddleOCR using the optional requirements file:
> `pip install -r requirements-optional.txt`
> Then rerun the benchmark script.

| Sample | Field | Label | Tesseract Found | PaddleOCR Found |
|---|---|---|---|---|
| invoice_1.png | invoice_number | INV-1001 | No | Yes |
| invoice_1.png | date | 2026-10-01 | No | Yes |
| invoice_1.png | total | $1,250.00 | No | Yes |
| invoice_2_scanned.png | invoice_number | 998877 | No | Yes |
| invoice_2_scanned.png | date | 12-05-2026 | No | Yes |
| invoice_2_scanned.png | total | 550.00 | No | Yes |
| receipt_3.png | invoice_number | R-12345 | No | Yes |
| receipt_3.png | date | 03/15/2026 | No | Yes |
| receipt_3.png | total | 89.99 | No | Yes |

## Summary

- **Tesseract Accuracy**: 0/9 (0.0%)
- **PaddleOCR Accuracy**: 9/9 (100.0%)

### Runtime averages

- **Tesseract Avg Time**: 0.006 sec
- **PaddleOCR Avg Time**: 9.485 sec

## Recommendation

Consider adopting PaddleOCR if accuracy gains justify the performance overhead, but Tesseract remains a fast, reliable baseline.