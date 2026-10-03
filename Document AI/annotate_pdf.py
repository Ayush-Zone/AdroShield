import fitz
import sys
from collections import Counter
from pathlib import Path

def annotate_pdf(pdf_path, out_image_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # 1. Analyze fonts
    text_dict = page.get_text("dict")
    spans = []
    font_counter = Counter()
    
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    font = span.get("font")
                    color = span.get("color")
                    bbox = span.get("bbox")
                    spans.append({
                        "text": text,
                        "font": font,
                        "color": color,
                        "bbox": fitz.Rect(bbox)
                    })
                    font_counter[font] += 1
    
    # Heuristic: dominant fonts are > 10% of total spans
    total_spans = len(spans)
    dominant_fonts = {f for f, c in font_counter.items() if c > max(2, total_spans * 0.05)}
    
    # 2. Draw annotations
    # We will use Red for "suspected text" (like PAID, APPROVED, or mismatched totals)
    # We will use Yellow for "font changes" (rare fonts)
    
    for span in spans:
        is_font_anomaly = span["font"] not in dominant_fonts
        
        text_lower = span["text"].lower()
        is_suspect_text = (
            "paid" in text_lower or 
            "approved" in text_lower or 
            "1,20,000" in text_lower or
            "1,45,500" in text_lower or 
            "26,190" in text_lower or
            span["color"] == 16711680  # Pure red in integer representation (if any)
        )
        
        if is_suspect_text:
            # Draw Red box for suspected text
            rect = span["bbox"]
            page.draw_rect(rect, color=(1, 0, 0), width=2)
        elif is_font_anomaly:
            # Draw Yellow box for font change
            rect = span["bbox"]
            page.draw_rect(rect, color=(1, 1, 0), width=2)

    # 3. Save as image
    pix = page.get_pixmap(dpi=150)
    pix.save(out_image_path)
    doc.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: annotate_pdf.py <input.pdf> <output.png>")
        sys.exit(1)
    annotate_pdf(sys.argv[1], sys.argv[2])
