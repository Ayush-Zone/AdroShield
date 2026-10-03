"""Face detection layer for Identity AI.

Evaluates preprocessed ID document and selfie images to locate faces,
enforcing triage logic:
- Exactly 1 face: status 'ok' (eligible for downstream matching)
- 0 faces: status 'inconclusive', indicator 'NO_FACE_DETECTED'
- >1 faces: status 'inconclusive', indicator 'MULTIPLE_FACES_DETECTED'
- Failure/corrupt: status 'error'
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

try:
    from .preprocessor import PreprocessingResult, preprocess_image
except ImportError:
    from preprocessor import PreprocessingResult, preprocess_image


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box coordinates for a detected face.

    Coordinates represent top-left origin (x, y) along with width and height.
    """

    x: int
    y: int
    width: int
    height: int

    @property
    def xmin(self) -> int:
        """Left boundary."""
        return self.x

    @property
    def ymin(self) -> int:
        """Top boundary."""
        return self.y

    @property
    def xmax(self) -> int:
        """Right boundary."""
        return self.x + self.width

    @property
    def ymax(self) -> int:
        """Bottom boundary."""
        return self.y + self.height

    def to_tuple(self) -> Tuple[int, int, int, int]:
        """Return (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class FaceDetectionResult:
    """Structured result returned by the face detection layer.

    Attributes:
        status: High-level outcome ('ok', 'inconclusive', or 'error').
        face_count: Total number of detected faces.
        bounding_boxes: List of BoundingBox objects for detected faces.
        indicator: Triage indicator code (e.g. 'NO_FACE_DETECTED',
                   'MULTIPLE_FACES_DETECTED') when inconclusive or error.
        message: Human-readable diagnostic description.
    """

    status: str
    face_count: int
    bounding_boxes: List[BoundingBox]
    indicator: Optional[str] = None
    message: str = ""


class BaseFaceDetector(ABC):
    """Abstract base class defining the face detection interface.

    Allows swapping underlying detection implementations (e.g. Haar cascades,
    MediaPipe, RetinaFace) without altering downstream integration contracts.
    """

    @abstractmethod
    def detect_raw(self, image: Image.Image) -> List[BoundingBox]:
        """Detect faces on a verified RGB PIL Image.

        Args:
            image: Clean 3-channel RGB PIL Image.

        Returns:
            List of BoundingBox instances representing detected face boundaries.
        """
        raise NotImplementedError

    def detect_faces(self, input_image: Any) -> FaceDetectionResult:
        """Execute face detection and apply standard ADROSHIELD triage rules.

        Triage Rules:
        - Exactly 1 face: status 'ok', face_count 1, bounding_boxes populated.
        - 0 faces: status 'inconclusive', indicator 'NO_FACE_DETECTED', face_count 0.
        - >1 faces: status 'inconclusive', indicator 'MULTIPLE_FACES_DETECTED', face_count N.
        - Invalid/corrupt inputs: status 'error'.

        Args:
            input_image: PIL Image, PreprocessingResult, or filesystem path (str/Path).

        Returns:
            FaceDetectionResult with status, triage indicator, and coordinates.
        """
        try:
            # 1. Ingestion and resolution to RGB PIL Image
            target_image: Optional[Image.Image] = None

            if isinstance(input_image, PreprocessingResult):
                if input_image.status != "ok" or input_image.image is None:
                    return FaceDetectionResult(
                        status="error",
                        face_count=0,
                        bounding_boxes=[],
                        indicator="PREPROCESSING_FAILED",
                        message=f"Preprocessing failed: {input_image.message}",
                    )
                target_image = input_image.image

            elif isinstance(input_image, (str, Path)):
                prep = preprocess_image(input_image)
                if prep.status != "ok" or prep.image is None:
                    return FaceDetectionResult(
                        status="error",
                        face_count=0,
                        bounding_boxes=[],
                        indicator="INPUT_PREPROCESSING_ERROR",
                        message=prep.message,
                    )
                target_image = prep.image

            elif isinstance(input_image, Image.Image):
                if input_image.mode != "RGB":
                    prep = preprocess_image(input_image)
                    if prep.status != "ok" or prep.image is None:
                        return FaceDetectionResult(
                            status="error",
                            face_count=0,
                            bounding_boxes=[],
                            indicator="CONVERSION_FAILED",
                            message="Unable to normalize PIL image to RGB.",
                        )
                    target_image = prep.image
                else:
                    target_image = input_image

            else:
                return FaceDetectionResult(
                    status="error",
                    face_count=0,
                    bounding_boxes=[],
                    indicator="INVALID_INPUT_TYPE",
                    message=(
                        f"Unsupported input type '{type(input_image).__name__}'. "
                        "Expected PIL.Image, PreprocessingResult, or file path."
                    ),
                )

            # 2. Raw detection execution
            raw_boxes = self.detect_raw(target_image)
            face_count = len(raw_boxes)

            # 3. Standard triage logic
            if face_count == 1:
                return FaceDetectionResult(
                    status="ok",
                    face_count=1,
                    bounding_boxes=raw_boxes,
                    indicator=None,
                    message="Exactly one face detected.",
                )
            elif face_count == 0:
                return FaceDetectionResult(
                    status="inconclusive",
                    face_count=0,
                    bounding_boxes=[],
                    indicator="NO_FACE_DETECTED",
                    message="No faces detected in the image.",
                )
            else:
                return FaceDetectionResult(
                    status="inconclusive",
                    face_count=face_count,
                    bounding_boxes=raw_boxes,
                    indicator="MULTIPLE_FACES_DETECTED",
                    message=f"Multiple faces ({face_count}) detected in the image.",
                )

        except Exception as exc:
            return FaceDetectionResult(
                status="error",
                face_count=0,
                bounding_boxes=[],
                indicator="DETECTION_EXCEPTION",
                message=f"Unexpected error during face detection: {exc}",
            )


class HaarCascadeFaceDetector(BaseFaceDetector):
    """Lightweight frontal face detector using OpenCV Haar Cascades.

    Operates without heavy deep-learning dependencies or GPU acceleration.
    """

    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 4,
        min_size: Tuple[int, int] = (30, 30),
    ) -> None:
        """Initialize the Haar Cascade classifier.

        Args:
            cascade_path: Path to frontal face XML cascade file. Defaults
                          to OpenCV's built-in default frontal face cascade.
            scale_factor: Parameter specifying how much the image size is
                          reduced at each image scale.
            min_neighbors: Parameter specifying how many neighbors each candidate
                           rectangle should have to retain it.
            min_size: Minimum possible object size. Objects smaller are ignored.
        """
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

        self._classifier = cv2.CascadeClassifier(cascade_path)
        if self._classifier.empty():
            raise RuntimeError(f"Failed to load Haar Cascade from path: {cascade_path}")

        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

    def detect_raw(self, image: Image.Image) -> List[BoundingBox]:
        """Detect faces on an RGB PIL Image using Haar cascades."""
        np_image = np.array(image)
        # Convert RGB to Grayscale for Haar detection
        if len(np_image.shape) == 3 and np_image.shape[2] == 3:
            gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_image

        faces = self._classifier.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )

        boxes: List[BoundingBox] = []
        if len(faces) > 0:
            for x, y, w, h in faces:
                boxes.append(BoundingBox(x=int(x), y=int(y), width=int(w), height=int(h)))

        return boxes


# Module-level default detector instance (lazy initialized)
_DEFAULT_DETECTOR: Optional[HaarCascadeFaceDetector] = None


def get_default_detector() -> HaarCascadeFaceDetector:
    """Retrieve or initialize the singleton default HaarCascadeFaceDetector."""
    global _DEFAULT_DETECTOR
    if _DEFAULT_DETECTOR is None:
        _DEFAULT_DETECTOR = HaarCascadeFaceDetector()
    return _DEFAULT_DETECTOR


def detect_faces(
    image_input: Any,
    detector: Optional[BaseFaceDetector] = None,
) -> FaceDetectionResult:
    """Convenience function to detect faces on an input image.

    Args:
        image_input: PIL Image, PreprocessingResult, or file path.
        detector: Custom BaseFaceDetector instance (defaults to HaarCascadeFaceDetector).

    Returns:
        Structured FaceDetectionResult.
    """
    active_detector = detector if detector is not None else get_default_detector()
    return active_detector.detect_faces(image_input)
