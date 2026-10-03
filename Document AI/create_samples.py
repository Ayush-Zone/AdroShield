import os
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont

samples_dir = Path(os.path.expanduser("~/Desktop/samples"))
samples_dir.mkdir(parents=True, exist_ok=True)

def create_invoice_pdf(path, total="100.00", subtotal="80.00", tax="20.00", date="2023-10-01", num="INV-1001", producer="ReportLab"):
    c = canvas.Canvas(str(path), pagesize=letter)
    if producer:
        c.setCreator(producer)
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "INVOICE")
    c.drawString(100, 680, f"Invoice Number: {num}")
    c.drawString(100, 660, f"Date: {date}")
    
    c.drawString(100, 600, "Description            Amount")
    c.drawString(100, 580, "Services               $80.00")
    
    c.drawString(100, 540, f"Subtotal: ${subtotal}")
    c.drawString(100, 520, f"Tax: ${tax}")
    c.drawString(100, 500, f"Total: ${total}")
    c.save()

def create_image(path, text, format="JPEG", draw_patch=False):
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Just draw simple text
    d.text((50, 50), text, fill=(0,0,0))
    
    if draw_patch:
        # draw a small rectangle with different text to simulate edit
        d.rectangle([200, 190, 280, 210], fill=(240, 240, 240))
        d.text((205, 195), "$999.00", fill=(10, 10, 10))
        
    # Save a couple of times to simulate jpeg history if JPEG
    if format == "JPEG":
        img.save(str(path), "JPEG", quality=90)
        img2 = Image.open(str(path))
        img2.save(str(path), "JPEG", quality=80)
    else:
        img.save(str(path), format)

def main():
    # 1. Clean digital invoice PDF
    create_invoice_pdf(samples_dir / "clean_invoice.pdf")
    
    # 2. Same invoice with only the total edited (mismatch)
    create_invoice_pdf(samples_dir / "edited_total.pdf", total="999.00")
    
    # 3. Same invoice with total, subtotal, and tax all edited consistently
    create_invoice_pdf(samples_dir / "edited_consistent.pdf", total="500.00", subtotal="400.00", tax="100.00")
    
    # 4. Phone photo (JPEG) of an invoice
    text_inv = "INVOICE\n\nInvoice Number: INV-2002\nDate: 2023-11-01\n\nSubtotal: $200.00\nTax: $50.00\nTotal: $250.00"
    create_image(samples_dir / "invoice_photo.jpg", text_inv, "JPEG")
    
    # 5. Same photo edited (JPEG)
    create_image(samples_dir / "invoice_edited.jpg", text_inv, "JPEG", draw_patch=True)
    
    # 6. Screenshot (PNG)
    create_image(samples_dir / "screenshot.png", text_inv, "PNG")
    
    # 7. ID card photo
    create_image(samples_dir / "id_card.jpg", "DRIVERS LICENSE\nName: John Doe\nDOB: 01/01/1990", "JPEG")
    
    # 8. Blank page, empty file, corrupt PDF
    create_invoice_pdf(samples_dir / "blank.pdf", total="", subtotal="", tax="")
    (samples_dir / "empty.txt").write_text("")
    (samples_dir / "corrupt.pdf").write_bytes(b"%PDF-1.4\n%corrupt file\n")
    
    print(f"Created {len(list(samples_dir.iterdir()))} files in {samples_dir}")

if __name__ == "__main__":
    main()
