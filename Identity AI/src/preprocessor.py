"""Image preprocessor for Identity AI.

Prepares validated ID document and selfie images for downstream face detection
and comparison models. Handles safe opening, EXIF orientation correction,
and strict RGB mode normalization.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageOps

try:
    from .validator import ValidationStatus, validate_image
except ImportError:
    from validator import ValidationStatus, validate_image



@dataclass(frozen=True)
class PreprocessingResult:
    """Structured result returned by the image preprocessor.

    Attributes:
        status: Operational outcome ('ok' or 'error').
        image: Preprocessed RGB PIL Image object if successful, None otherwise.
        original_mode: Color mode of the image prior to conversion (e.g. 'RGBA', 'L').
        final_mode: Guaranteed color mode ('RGB' on success, empty on error).
        dimensions: Output image dimensions as (width, height) if successful.
        orientation_applied: True if an EXIF orientation transformation was applied.
        message: Diagnostic description of the preprocessing operation.
    """

    status: str
    image: Optional[Image.Image]
    original_mode: Optional[str]
    final_mode: str
    dimensions: Optional[Tuple[int, int]]
    orientation_applied: bool
    message: str


def preprocess_image(
    input_image: Union[str, Path, Image.Image],
) -> PreprocessingResult:
    """Preprocess an input image for future facial feature extraction.

    Pipeline operations:
    1. Validation (if path provided) and safe loading.
    2. EXIF orientation correction (e.g., auto-rotating mobile camera selfies).
    3. Normalization to standard 3-channel RGB mode (compositing transparency onto white).
    4. Deterministic image packaging without altering content integrity.

    Args:
        input_image: Filesystem path (str/Path) or an existing PIL Image instance.

    Returns:
        PreprocessingResult containing the processed RGB PIL Image or error details.
    """
    raw_img: Optional[Image.Image] = None

    try:
        # Step 1: Ingestion & Validation
        if isinstance(input_image, (str, Path)):
            validation = validate_image(input_image)
            if not validation.is_valid or validation.status != ValidationStatus.OK:
                return PreprocessingResult(
                    status="error",
                    image=None,
                    original_mode=None,
                    final_mode="",
                    dimensions=None,
                    orientation_applied=False,
                    message=f"Preprocessing aborted: {validation.message}",
                )

            # Safely open and load image into memory
            loaded = Image.open(input_image)
            loaded.load()
            raw_img = loaded
        elif isinstance(input_image, Image.Image):
            raw_img = input_image.copy()
        else:
            return PreprocessingResult(
                status="error",
                image=None,
                original_mode=None,
                final_mode="",
                dimensions=None,
                orientation_applied=False,
                message=f"Unsupported input type '{type(input_image).__name__}'. Expected str, Path, or PIL.Image.",
            )

        original_mode = raw_img.mode
        original_size = raw_img.size

        # Step 2: EXIF Orientation Transpose
        # Mobile selfies and ID captures often carry EXIF rotation tags (1-8).
        orientation_applied = False
        try:
            transposed = ImageOps.exif_transpose(raw_img)
            if transposed is not None and transposed is not raw_img:
                if transposed.size != original_size or transposed != raw_img:
                    orientation_applied = True
                raw_img = transposed
        except Exception:
            # If EXIF reading fails, continue with original orientation without crashing
            orientation_applied = False

        # Step 3: Color Mode Normalization to RGB
        # Downstream face detectors (FaceNet, etc.) expect 3-channel RGB.
        if raw_img.mode == "RGB":
            processed_img = raw_img.copy()
        elif raw_img.mode in ("RGBA", "LA"):
            # Alpha composite over clean neutral white background to avoid black background artifacts
            background = Image.new("RGB", raw_img.size, (255, 255, 255))
            alpha_channel = raw_img.convert("RGBA").split()[3]
            background.paste(raw_img, mask=alpha_channel)
            processed_img = background
        elif raw_img.mode == "P" and "transparency" in raw_img.info:
            # Palette with transparency
            rgba = raw_img.convert("RGBA")
            background = Image.new("RGB", raw_img.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[3])
            processed_img = background
        else:
            # Grayscale ('L'), Palette ('P'), CMYK, etc.
            processed_img = raw_img.convert("RGB")

        final_dimensions = (processed_img.width, processed_img.height)

        return PreprocessingResult(
            status="ok",
            image=processed_img,
            original_mode=original_mode,
            final_mode="RGB",
            dimensions=final_dimensions,
            orientation_applied=orientation_applied,
            message="Image successfully preprocessed and normalized to RGB.",
        )

    except Exception as exc:
        return PreprocessingResult(
            status="error",
            image=None,
            original_mode=None,
            final_mode="",
            dimensions=None,
            orientation_applied=False,
            message=f"Unexpected error during image preprocessing: {exc}",
        )
    finally:
        if raw_img is not None and hasattr(raw_img, "close"):
            try:
                raw_img.close()
            except Exception:
                pass
