"""Image validator for Identity AI.

Handles Phase 1 input validation for ID documents and selfie images.
Checks file existence, format support, file integrity, and dimensions
without raising unhandled exceptions.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Set, Tuple, Union

from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png"}
SUPPORTED_FORMATS: Set[str] = {"JPEG", "PNG"}


class ValidationStatus(str, Enum):
    """Standardized validation status states."""

    OK = "ok"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


@dataclass(frozen=True)
class ImageValidationResult:
    """Structured result returned by the image validator.

    Attributes:
        status: High-level operational state ('ok', 'inconclusive', or 'error').
        is_valid: True if image passed all checks and is safe for preprocessing.
        message: Human-readable diagnostic description of the result.
        file_path: Resolved path to the inspected file, if provided.
        format: Detected image format (e.g. 'JPEG', 'PNG') if readable.
        dimensions: Image dimensions as (width, height) if readable.
    """

    status: ValidationStatus
    is_valid: bool
    message: str
    file_path: Optional[str] = None
    format: Optional[str] = None
    dimensions: Optional[Tuple[int, int]] = None


def validate_image(image_path: Union[str, Path, None]) -> ImageValidationResult:
    """Validate an input image path for the Identity AI pipeline.

    Checks:
    1. A valid path string/Path is supplied.
    2. The target exists on the filesystem and is a regular file.
    3. The file extension is in the supported set (.jpg, .jpeg, .png).
    4. The file has non-zero size.
    5. The file can be safely opened and decoded by the image library.
    6. The detected image format matches the supported formats.

    Args:
        image_path: Filesystem path to the image file to validate.

    Returns:
        ImageValidationResult containing status, validation flag, and metadata.
    """
    # 1. Path presence check
    if image_path is None:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message="No image path was supplied.",
        )

    str_path = str(image_path).strip()
    if not str_path:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message="Image path cannot be empty or whitespace.",
        )

    try:
        path = Path(str_path)
    except Exception as exc:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"Invalid path specification: {exc}",
            file_path=str_path,
        )

    # 2. Filesystem existence check
    if not path.exists():
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"File not found at path: {path}",
            file_path=str(path),
        )

    if not path.is_file():
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"Path is not a regular file: {path}",
            file_path=str(path),
        )

    # 3. Extension check
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=(
                f"Unsupported file extension '{suffix}'. "
                f"Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}"
            ),
            file_path=str(path),
        )

    # 4. Non-zero size check
    try:
        if path.stat().st_size == 0:
            return ImageValidationResult(
                status=ValidationStatus.ERROR,
                is_valid=False,
                message="Image file is empty (0 bytes).",
                file_path=str(path),
            )
    except OSError as exc:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"Unable to read file metadata: {exc}",
            file_path=str(path),
        )

    # 5 & 6. Image decodability and format check
    try:
        with Image.open(path) as img:
            detected_format = (img.format or "").upper()
            if detected_format not in SUPPORTED_FORMATS:
                return ImageValidationResult(
                    status=ValidationStatus.ERROR,
                    is_valid=False,
                    message=(
                        f"Detected format '{detected_format}' does not match "
                        f"supported image types: {sorted(SUPPORTED_FORMATS)}."
                    ),
                    file_path=str(path),
                    format=detected_format or None,
                )

            # Ensure image integrity and dimensions can be loaded safely
            img.verify()

        # Re-open to read dimensions and load bitmap (verify closes/invalidates the stream)
        with Image.open(path) as img:
            img.load()
            dimensions = (img.width, img.height)

            if img.width <= 0 or img.height <= 0:
                return ImageValidationResult(
                    status=ValidationStatus.INCONCLUSIVE,
                    is_valid=False,
                    message=f"Invalid image dimensions: {dimensions}.",
                    file_path=str(path),
                    format=detected_format,
                    dimensions=dimensions,
                )

            return ImageValidationResult(
                status=ValidationStatus.OK,
                is_valid=True,
                message="Image is valid and readable.",
                file_path=str(path),
                format=detected_format,
                dimensions=dimensions,
            )

    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"Corrupt or unreadable image file: {exc}",
            file_path=str(path),
        )
    except Exception as exc:
        return ImageValidationResult(
            status=ValidationStatus.ERROR,
            is_valid=False,
            message=f"Unexpected error while validating image: {exc}",
            file_path=str(path),
        )
