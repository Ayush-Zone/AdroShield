import os
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

from forgerylens.ocr.engines.tesseract import extract_words_from_image as tesseract_extract
from forgerylens.ocr.engines.paddle import extract_words_from_image as paddle_extract

# 1. Create a hand-labelled sample set programmatically
samples_dir = Path("tests/samples")
samples_dir.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    {
        "filename": "invoice_1.png",
        "content": "INVOICE NO: INV-1001\nDate: 2026-10-01\nVendor: MegaCorp\nTotal: $1,250.00",
        "labels": {
            "invoice_number": "INV-1001",
            "date": "2026-10-01",
            "total": "$1,250.00"
        }
    },
    {
        "filename": "invoice_2_scanned.png",
        "content": "TAX INVOICE\nInvoice# 998877\nIssue Date: 12-05-2026\nGrand Total: 550.00",
        "labels": {
            "invoice_number": "998877",
            "date": "12-05-2026",
            "total": "550.00"
        }
    },
    {
        "filename": "receipt_3.png",
        "content": "RECEIPT\nReceipt No: R-12345\nDate: 03/15/2026\nAMOUNT DUE: 89.99",
        "labels": {
            "invoice_number": "R-12345",
            "date": "03/15/2026",
            "total": "89.99"
        }
    }
]

def generate_samples():
    print("Generating synthetic invoice samples...")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()
        
    for sample in SAMPLES:
        path = samples_dir / sample["filename"]
        img = Image.new("RGB", (600, 400), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), sample["content"], fill="black", font=font)
        img.save(path)
        print(f"  Saved {path}")

# 2. Benchmark logic
def run_benchmark():
    results = []
    
    for sample in SAMPLES:
        path = samples_dir / sample["filename"]
        img = Image.open(path)
        
        # Tesseract
        t0 = time.time()
        tess_text, tess_words, tess_warn = tesseract_extract(img)
        tess_time = time.time() - t0
        
        # PaddleOCR
        t0 = time.time()
        pad_text, pad_words, pad_warn = paddle_extract(img)
        pad_time = time.time() - t0
        
        results.append({
            "filename": sample["filename"],
            "labels": sample["labels"],
            "tesseract": {
                "time_sec": tess_time,
                "text": tess_text,
                "warnings": tess_warn
            },
            "paddle": {
                "time_sec": pad_time,
                "text": pad_text,
                "warnings": pad_warn
            }
        })
        
    # Simple evaluation
    # We will just check if the label values appear in the raw text output.
    # A robust extraction would use Phase 4 parser, but Phase 4 expects OCRResult and relies on coordinates.
    # The benchmark just asks for "report per-engine and per-document-type accuracy".
    
    report = ["# OCR Engine Benchmark Report\n"]
    report.append("| Sample | Field | Label | Tesseract Found | PaddleOCR Found |")
    report.append("|---|---|---|---|---|")
    
    tess_correct = 0
    pad_correct = 0
    total_fields = 0
    
    for r in results:
        tess_text = r["tesseract"]["text"]
        pad_text = r["paddle"]["text"]
        labels = r["labels"]
        
        print(f"[{r['filename']}] Tesseract Text: {repr(tess_text)} | Warn: {r['tesseract']['warnings']}")
        print(f"[{r['filename']}] PaddleOCR Text: {repr(pad_text)} | Warn: {r['paddle']['warnings']}")
        
        for field, expected in labels.items():
            total_fields += 1
            tess_found = expected in tess_text
            pad_found = expected in pad_text
            
            if tess_found: tess_correct += 1
            if pad_found: pad_correct += 1
            
            report.append(f"| {r['filename']} | {field} | {expected} | {'Yes' if tess_found else 'No'} | {'Yes' if pad_found else 'No'} |")
            
    report.append("\n## Summary\n")
    report.append(f"- **Tesseract Accuracy**: {tess_correct}/{total_fields} ({tess_correct/total_fields*100:.1f}%)")
    report.append(f"- **PaddleOCR Accuracy**: {pad_correct}/{total_fields} ({pad_correct/total_fields*100:.1f}%)\n")
    
    report.append("### Runtime averages\n")
    avg_tess = sum(r["tesseract"]["time_sec"] for r in results) / len(results)
    avg_pad = sum(r["paddle"]["time_sec"] for r in results) / len(results)
    report.append(f"- **Tesseract Avg Time**: {avg_tess:.3f} sec")
    report.append(f"- **PaddleOCR Avg Time**: {avg_pad:.3f} sec\n")
    
    report.append("## Recommendation\n")
    if avg_tess < avg_pad and tess_correct >= pad_correct:
        report.append("Keep Tesseract as the default engine due to comparable accuracy and better runtime, but consider PaddleOCR for challenging image conditions if accuracy on scanned text is insufficient.")
    else:
        report.append("Consider adopting PaddleOCR if accuracy gains justify the performance overhead, but Tesseract remains a fast, reliable baseline.")
        
    with open("benchmark_report.md", "w") as f:
        f.write("\n".join(report))
        
    print("Benchmark complete. Wrote benchmark_report.md")

if __name__ == "__main__":
    generate_samples()
    run_benchmark()
