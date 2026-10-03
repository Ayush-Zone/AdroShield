"""Native PDF text extraction engine."""

import logging
from typing import List, Tuple

from forgerylens.contracts.ocr import OCRWord

logger = logging.getLogger(__name__)


def extract_words_from_pdf_page(page, page_width: float, page_height: float) -> Tuple[str, List[OCRWord], List[str]]:
    """Extract native text and word-level information from a PyMuPDF page.
    
    Args:
        page: A fitz.Page object.
        page_width: The width of the page in points.
        page_height: The height of the page in points.
        
    Returns:
        (full_text, list_of_OCRWord, warnings)
    """
    warnings: List[str] = []
    words: List[OCRWord] = []
    full_text = ""

    try:
        # get_text("words") returns: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        # Coordinates are in points, relative to the page's top-left corner.
        word_tuples = page.get_text("words")
        
        texts = []
        for wt in word_tuples:
            x0, y0, x1, y1, text, _, _, _ = wt
            
            if not text.strip():
                continue
                
            width = x1 - x0
            height = y1 - y0
            
            # Normalize coordinates
            norm_x = min(max(x0 / page_width, 0.0), 1.0) if page_width > 0 else 0.0
            norm_y = min(max(y0 / page_height, 0.0), 1.0) if page_height > 0 else 0.0
            norm_w = min(max(width / page_width, 0.0), 1.0) if page_width > 0 else 0.0
            norm_h = min(max(height / page_height, 0.0), 1.0) if page_height > 0 else 0.0
            
            word = OCRWord(
                text=text,
                confidence=None,  # Native digital text has no OCR confidence
                x=norm_x,
                y=norm_y,
                width=norm_w,
                height=norm_h
            )
            words.append(word)
            texts.append(text)
            
        full_text = " ".join(texts)

    except Exception as e:
        warnings.append(f"Native PDF extraction failed: {str(e)}")

    return full_text, words, warnings
