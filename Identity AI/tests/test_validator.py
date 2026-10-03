"""Tests for Identity AI image validator.

Validates that only supported, readable, uncorrupted images pass validation,
and that missing, corrupt, or unsupported files fail gracefully without crashes.
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

from validator import ValidationStatus, validate_image


def test_valid_jpeg(tmp_path: Path):
    """Confirm valid synthetic JPEG file passes validation."""
    img_path = tmp_path / "synthetic_id.jpg"
    img = Image.new("RGB", (150, 100), color=(100, 150, 200))
    img.save(img_path, format="JPEG")

    result = validate_image(img_path)

    assert result.status == ValidationStatus.OK
    assert result.is_valid is True
    assert result.format == "JPEG"
    assert result.dimensions == (150, 100)
    assert "valid" in result.message.lower()


def test_valid_png(tmp_path: Path):
    """Confirm valid synthetic PNG file passes validation."""
    img_path = tmp_path / "synthetic_selfie.png"
    img = Image.new("RGB", (200, 200), color=(50, 80, 120))
    img.save(img_path, format="PNG")

    result = validate_image(img_path)

    assert result.status == ValidationStatus.OK
    assert result.is_valid is True
    assert result.format == "PNG"
    assert result.dimensions == (200, 200)


def test_missing_file(tmp_path: Path):
    """Confirm missing file returns error result with clear message."""
    missing_path = tmp_path / "does_not_exist.jpg"

    result = validate_image(missing_path)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "not found" in result.message.lower()


def test_none_and_empty_paths():
    """Confirm None, empty, and whitespace paths return error status."""
    for bad_input in (None, "", "   "):
        result = validate_image(bad_input)
        assert result.status == ValidationStatus.ERROR
        assert result.is_valid is False


def test_directory_as_path(tmp_path: Path):
    """Confirm passing a directory path instead of a file fails safely."""
    dir_path = tmp_path / "test_folder.jpg"
    dir_path.mkdir()

    result = validate_image(dir_path)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "not a regular file" in result.message.lower()


@pytest.mark.parametrize("ext", [".gif", ".bmp", ".txt", ".pdf", ".webp", ".tiff"])
def test_unsupported_extensions(tmp_path: Path, ext: str):
    """Confirm unsupported image formats are rejected."""
    unsupported_file = tmp_path / f"document{ext}"
    unsupported_file.write_bytes(b"dummy content")

    result = validate_image(unsupported_file)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "unsupported file extension" in result.message.lower()


def test_empty_zero_byte_file(tmp_path: Path):
    """Confirm empty (0-byte) image file fails validation safely."""
    empty_file = tmp_path / "empty.jpg"
    empty_file.touch()

    result = validate_image(empty_file)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "empty" in result.message.lower()


def test_corrupted_image_file(tmp_path: Path):
    """Confirm corrupted file content fails safely without uncaught exception."""
    corrupt_file = tmp_path / "corrupted.jpg"
    corrupt_file.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00corrupted_garbage_bytes_here")

    result = validate_image(corrupt_file)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "corrupt" in result.message.lower() or "unreadable" in result.message.lower()


def test_format_spoofing(tmp_path: Path):
    """Confirm file with valid BMP bytes named as .jpg is detected and rejected."""
    spoofed_file = tmp_path / "spoofed.jpg"
    bmp_img = Image.new("RGB", (50, 50), color=(255, 0, 0))
    bmp_img.save(spoofed_file, format="BMP")

    result = validate_image(spoofed_file)

    assert result.status == ValidationStatus.ERROR
    assert result.is_valid is False
    assert "does not match supported" in result.message.lower()
