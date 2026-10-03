"""Tests for Identity AI image preprocessor.

Validates that valid images are safely opened, orientation is handled,
color channels are strictly normalized to RGB, and invalid inputs fail gracefully.
All test fixtures use synthetic programmatic images without sensitive data.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

# Ensure Identity AI/src is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from preprocessor import PreprocessingResult, preprocess_image
from validator import validate_image


def test_preprocess_valid_jpeg(tmp_path: Path):
    """Confirm valid JPEG is preprocessed cleanly to RGB."""
    img_path = tmp_path / "valid.jpg"
    img = Image.new("RGB", (120, 160), color=(128, 64, 32))
    img.save(img_path, format="JPEG")

    result = preprocess_image(img_path)

    assert result.status == "ok"
    assert result.image is not None
    assert result.final_mode == "RGB"
    assert result.image.mode == "RGB"
    assert result.dimensions == (120, 160)


def test_preprocess_rgba_png_converts_to_rgb(tmp_path: Path):
    """Confirm RGBA image with alpha channel is converted to 3-channel RGB."""
    img_path = tmp_path / "transparent.png"
    # Create RGBA image with semi-transparent pixel
    rgba_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    rgba_img.save(img_path, format="PNG")

    result = preprocess_image(img_path)

    assert result.status == "ok"
    assert result.image is not None
    assert result.original_mode == "RGBA"
    assert result.final_mode == "RGB"
    assert result.image.mode == "RGB"
    assert len(result.image.getbands()) == 3


def test_preprocess_grayscale_converts_to_rgb(tmp_path: Path):
    """Confirm grayscale (L mode) image is normalized to 3-channel RGB."""
    img_path = tmp_path / "grayscale.png"
    gray_img = Image.new("L", (80, 80), color=120)
    gray_img.save(img_path, format="PNG")

    result = preprocess_image(img_path)

    assert result.status == "ok"
    assert result.image is not None
    assert result.original_mode == "L"
    assert result.final_mode == "RGB"
    assert result.image.mode == "RGB"
    assert result.image.getbands() == ("R", "G", "B")


def test_preprocess_pil_image_direct():
    """Confirm directly passing a PIL Image instance works deterministically."""
    direct_img = Image.new("RGBA", (50, 50), color=(0, 200, 100, 255))

    result = preprocess_image(direct_img)

    assert result.status == "ok"
    assert result.image is not None
    assert result.final_mode == "RGB"
    assert result.image.mode == "RGB"


def test_preprocess_exif_orientation_handling(tmp_path: Path):
    """Confirm EXIF orientation transpose is handled gracefully."""
    img_path = tmp_path / "oriented.jpg"
    img = Image.new("RGB", (100, 200), color=(10, 20, 30))

    # Add EXIF orientation tag (Orientation = 6 implies 90-degree CW rotation)
    exif = img.getexif()
    exif[0x0112] = 6  # 0x0112 is EXIF Orientation tag
    img.save(img_path, format="JPEG", exif=exif)

    result = preprocess_image(img_path)

    assert result.status == "ok"
    assert result.image is not None
    assert result.final_mode == "RGB"
    # When orientation 6 is transposed, width and height swap: (100, 200) -> (200, 100)
    assert result.dimensions == (200, 100)
    assert result.orientation_applied is True


def test_preprocess_corrupted_file_fails_safely(tmp_path: Path):
    """Confirm corrupt file returns error result without crashing."""
    corrupt_path = tmp_path / "bad.png"
    corrupt_path.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt_content")

    result = preprocess_image(corrupt_path)

    assert result.status == "error"
    assert result.image is None
    assert "aborted" in result.message.lower() or "error" in result.message.lower()


def test_preprocess_invalid_input_type():
    """Confirm invalid input type (e.g. integer) is rejected safely."""
    result = preprocess_image(12345)  # type: ignore

    assert result.status == "error"
    assert result.image is None
    assert "unsupported input type" in result.message.lower()


def test_preprocessed_output_preserves_validity(tmp_path: Path):
    """Confirm that the preprocessed image output can be saved and passes validation."""
    src_path = tmp_path / "source.png"
    src_img = Image.new("RGB", (90, 110), color=(40, 70, 90))
    src_img.save(src_path, format="PNG")

    prep_result = preprocess_image(src_path)
    assert prep_result.status == "ok"
    assert prep_result.image is not None

    # Save output to disk and re-validate
    dest_path = tmp_path / "output_test.jpg"
    prep_result.image.save(dest_path, format="JPEG")

    val_result = validate_image(dest_path)
    assert val_result.status.value == "ok"
    assert val_result.is_valid is True
    assert val_result.dimensions == (90, 110)
