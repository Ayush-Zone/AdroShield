"""OCR orchestrator for document extraction."""

import logging
from pathlib import Path
from PIL import Image

from forgerylens.contracts.document import IngestedDocument, PageInfo
from forgerylens.contracts.enums import DocumentFormat, IngestionStatus
from forgerylens.contracts.ocr import (
    OCRResult,
    OCRPage,
    OCRExtractionMethod,
)
from forgerylens.ocr.engines.tesseract import extract_words_from_image

logger = logging.getLogger(__name__)


def _process_image_document(doc: IngestedDocument) -> OCRResult:
    """Process an image document using OCR."""
    result = OCRResult(
        document_id=doc.document_id,
        status=IngestionStatus.VALID,
        pages=[],
        warnings=list(doc.warnings),
        errors=list(doc.errors)
    )

    if not doc.is_valid:
        result.status = doc.status
        return result

    try:
        with Image.open(doc.source_path) as img:
            # Re-verify and ensure it's loaded safely for OCR
            img.load()
            
            full_text, words, warnings = extract_words_from_image(img)
            
            ocr_page = OCRPage(
                page_number=1,
                extraction_method=OCRExtractionMethod.TESSERACT_OCR,
                full_text=full_text,
                words=words,
                warnings=warnings
            )
            
            result.pages.append(ocr_page)
            
            if warnings:
                result.warnings.extend(warnings)
                
            if not words and not warnings:
                # Valid image, but no text found
                result.warnings.append("No text extracted from image.")
                
    except Exception as e:
        result.status = IngestionStatus.CORRUPT
        result.errors.append(f"Failed to process image for OCR: {str(e)}")

    return result


def _process_pdf_document(doc: IngestedDocument) -> OCRResult:
    """Process a PDF document natively or via rendering + OCR."""
    result = OCRResult(
        document_id=doc.document_id,
        status=IngestionStatus.VALID,
        pages=[],
        warnings=list(doc.warnings),
        errors=list(doc.errors)
    )

    if not doc.is_valid:
        result.status = doc.status
        return result

    try:
        import fitz
        from forgerylens.ocr.engines.pdf import extract_words_from_pdf_page
        
        pdf_doc = fitz.open(doc.source_path)
        
        for page_idx in range(len(pdf_doc)):
            page_num = page_idx + 1
            page = pdf_doc[page_idx]
            rect = page.rect
            width, height = rect.width, rect.height
            
            # 1. Try native PDF extraction
            full_text, words, warnings = extract_words_from_pdf_page(page, width, height)
            
            # 2. If no meaningful text found, assume scanned PDF and fallback to OCR
            # Heuristic: if less than 5 words, it might be mostly image-based.
            # But let's be strict: if it has 0 words, or if it has very few words and lots of images.
            # For simplicity, if we found native text, use it. Otherwise, render and OCR.
            if len(words) < 3:
                # Render page to Pixmap
                pix = page.get_pixmap(dpi=150) # Use 150 DPI for a balance of speed/quality
                # Convert Pixmap to PIL Image
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                
                ocr_full_text, ocr_words, ocr_warnings = extract_words_from_image(img)
                
                # Use OCR results if it found more words or if we had none natively
                if len(ocr_words) > len(words):
                    full_text = ocr_full_text
                    words = ocr_words
                    warnings.extend(ocr_warnings)
                    method = OCRExtractionMethod.TESSERACT_OCR
                else:
                    method = OCRExtractionMethod.NATIVE_PDF
            else:
                method = OCRExtractionMethod.NATIVE_PDF
                
            ocr_page = OCRPage(
                page_number=page_num,
                extraction_method=method,
                full_text=full_text,
                words=words,
                warnings=warnings
            )
            result.pages.append(ocr_page)
            
        pdf_doc.close()
        
    except ImportError:
        result.status = IngestionStatus.UNSUPPORTED
        result.errors.append("PyMuPDF (fitz) is required for PDF OCR processing.")
    except Exception as e:
        result.status = IngestionStatus.CORRUPT
        result.errors.append(f"Failed to process PDF for OCR: {str(e)}")

    # Check for partial failure / success
    if result.is_valid and not result.pages:
        result.status = IngestionStatus.UNREADABLE
        result.errors.append("Document processed but no pages could be analyzed.")

    return result


def extract_document_text(doc: IngestedDocument) -> OCRResult:
    """Orchestrate text extraction for an ingested document.
    
    Args:
        doc: An IngestedDocument from Phase 2.
        
    Returns:
        An OCRResult containing extracted pages, words, and coordinates.
    """
    if doc.format in (DocumentFormat.PNG, DocumentFormat.JPEG):
        return _process_image_document(doc)
    elif doc.format == DocumentFormat.PDF:
        return _process_pdf_document(doc)
        
    # Unsupported or unknown
    return OCRResult(
        document_id=doc.document_id,
        status=IngestionStatus.UNSUPPORTED if doc.is_valid else doc.status,
        pages=[],
        warnings=list(doc.warnings),
        errors=list(doc.errors) + [f"Unsupported format for extraction: {doc.format}"]
    )
