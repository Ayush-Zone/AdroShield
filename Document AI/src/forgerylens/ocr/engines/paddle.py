"""PaddleOCR engine implementation."""

import logging
from typing import List, Tuple
from PIL import Image
import numpy as np

from forgerylens.contracts.ocr import OCRWord

logger = logging.getLogger(__name__)

# Lazy initialization
_paddle_ocr_engine = None

def _get_engine():
    global _paddle_ocr_engine
    if _paddle_ocr_engine is None:
        from paddleocr import PaddleOCR
        # Initialize PaddleOCR engine
        _paddle_ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', enable_mkldnn=False)
    return _paddle_ocr_engine

def extract_words_from_image(img: Image.Image) -> Tuple[str, List[OCRWord], List[str]]:
    """Extract text and word-level information from an image using PaddleOCR.
    
    Args:
        img: The PIL Image to process.
        
    Returns:
        (full_text, list_of_OCRWord, warnings)
    """
    warnings: List[str] = []
    words: List[OCRWord] = []
    full_text = ""

    try:
        img_width, img_height = img.size
        
        if img_width == 0 or img_height == 0:
            warnings.append("Image has 0 width or height; cannot perform OCR.")
            return "", [], warnings

        # Convert PIL Image to BGR numpy array for PaddleOCR
        img_cv = np.array(img.convert('RGB'))[:, :, ::-1]

        engine = _get_engine()
        result = engine.ocr(img_cv)

        texts = []
        if result and len(result) > 0:
            res_dict = result[0]
            if isinstance(res_dict, dict) and "rec_texts" in res_dict:
                rec_texts = res_dict.get("rec_texts", [])
                rec_scores = res_dict.get("rec_scores", [])
                dt_polys = res_dict.get("dt_polys", [])
                
                for i in range(len(rec_texts)):
                    text = rec_texts[i]
                    conf = rec_scores[i] if i < len(rec_scores) else 0.0
                    box = dt_polys[i] if i < len(dt_polys) else None
                    
                    if box is not None:
                        xs = [pt[0] for pt in box]
                        ys = [pt[1] for pt in box]
                        left = min(xs)
                        top = min(ys)
                        width = max(xs) - left
                        height = max(ys) - top
                    else:
                        left = top = width = height = 0
                        
                    # Normalize coordinates (0.0 to 1.0)
                    norm_x = min(max(float(left) / img_width, 0.0), 1.0)
                    norm_y = min(max(float(top) / img_height, 0.0), 1.0)
                    norm_w = min(max(float(width) / img_width, 0.0), 1.0)
                    norm_h = min(max(float(height) / img_height, 0.0), 1.0)
                    
                    conf_val = float(conf) * 100.0

                    word = OCRWord(
                        text=text,
                        confidence=conf_val,
                        x=norm_x,
                        y=norm_y,
                        width=norm_w,
                        height=norm_h
                    )
                    words.append(word)
                    texts.append(text)
            else:
                for line in result[0]:
                    box, (text, conf) = line
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    left = min(xs)
                    top = min(ys)
                    width = max(xs) - left
                    height = max(ys) - top
                    
                    # Normalize coordinates (0.0 to 1.0)
                    norm_x = min(max(float(left) / img_width, 0.0), 1.0)
                    norm_y = min(max(float(top) / img_height, 0.0), 1.0)
                    norm_w = min(max(float(width) / img_width, 0.0), 1.0)
                    norm_h = min(max(float(height) / img_height, 0.0), 1.0)
                    
                    conf_val = float(conf) * 100.0

                    word = OCRWord(
                        text=text,
                        confidence=conf_val,
                        x=norm_x,
                        y=norm_y,
                        width=norm_w,
                        height=norm_h
                    )
                    words.append(word)
                    texts.append(text)
                
        full_text = " ".join(texts)

    except Exception as e:
        warnings.append(f"PaddleOCR failed: {str(e)}")

    return full_text, words, warnings
