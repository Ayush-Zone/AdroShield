"""Tesseract OCR engine implementation."""

import logging
from typing import List, Tuple
from PIL import Image
import pytesseract

from forgerylens.contracts.ocr import OCRWord

logger = logging.getLogger(__name__)


def extract_words_from_image(img: Image.Image) -> Tuple[str, List[OCRWord], List[str]]:
    """Extract text and word-level information from an image using Tesseract.
    
    Args:
        img: The PIL Image to process.
        
    Returns:
        (full_text, list_of_OCRWord, warnings)
    """
    warnings: List[str] = []
    words: List[OCRWord] = []
    full_text = ""

    try:
        # Convert to grayscale for better basic OCR if not already
        if img.mode not in ("L", "1"):
            img = img.convert("L")
            
        img_width, img_height = img.size
        
        # We need width and height to be valid for normalization
        if img_width == 0 or img_height == 0:
            warnings.append("Image has 0 width or height; cannot perform OCR.")
            return "", [], warnings

        # Extract data dictionary
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        # Build the full text by joining recognized words properly, but
        # image_to_string might give better paragraph formatting. 
        # For simplicity and exact correspondence, we will use the data dictionary.
        
        texts = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            # level 5 corresponds to word level in tesseract's TSV output
            if int(data["level"][i]) == 5 and text:
                conf_val = data["conf"][i]
                
                # Sometime tesseract returns -1 for confidence
                try:
                    conf = float(conf_val)
                    if conf < 0:
                        conf = 0.0
                except (ValueError, TypeError):
                    conf = 0.0
                    
                left = float(data["left"][i])
                top = float(data["top"][i])
                width = float(data["width"][i])
                height = float(data["height"][i])
                
                # Normalize coordinates (0.0 to 1.0)
                norm_x = min(max(left / img_width, 0.0), 1.0)
                norm_y = min(max(top / img_height, 0.0), 1.0)
                norm_w = min(max(width / img_width, 0.0), 1.0)
                norm_h = min(max(height / img_height, 0.0), 1.0)
                
                word = OCRWord(
                    text=text,
                    confidence=conf,
                    x=norm_x,
                    y=norm_y,
                    width=norm_w,
                    height=norm_h
                )
                words.append(word)
                texts.append(text)
                
        full_text = " ".join(texts)

    except Exception as e:
        warnings.append(f"Tesseract OCR failed: {str(e)}")

    return full_text, words, warnings
