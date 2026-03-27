"""
Jersey number recognition using EasyOCR.

Provides OCR-based jersey number extraction from basketball photos with
graceful degradation when EasyOCR is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from src.logging_config import get_logger
from src.types.errors import ImageProcessingError

if TYPE_CHECKING:
    from typing import Any

    from numpy.typing import NDArray

# Graceful degradation for EasyOCR
try:
    import easyocr

    HAS_EASYOCR = True
except ImportError:
    easyocr = None  # type: ignore[assignment]
    HAS_EASYOCR = False

# Graceful degradation for OpenCV
try:
    import cv2

    HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    HAS_CV2 = False

log = get_logger(__name__)


class JerseyOCR:
    """
    OCR-based jersey number recognition for basketball photos.

    Uses EasyOCR with preprocessing (CLAHE, denoising) to extract
    jersey numbers from images. Returns only valid 1-2 digit numbers
    (0-99) that meet the confidence threshold.

    Attributes:
        confidence_threshold: Minimum confidence for accepting OCR results.
        use_gpu: Whether to use GPU acceleration for OCR.
        _reader: Lazy-loaded EasyOCR reader instance.

    Example:
        >>> ocr = JerseyOCR(confidence_threshold=0.6)
        >>> results = ocr.recognize("./images/cropped_player.jpg")
        >>> # Returns: [("23", 0.87), ("6", 0.72)]
    """

    # OCR configuration
    ALLOWLIST = "0123456789"  # Numbers only
    MIN_DIGITS = 1
    MAX_DIGITS = 2  # Jersey numbers are 0-99

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        use_gpu: bool = False,
        clahe_clip_limit: float = 2.0,
        clahe_grid_size: tuple[int, int] = (8, 8),
    ):
        """
        Initialize JerseyOCR with configuration.

        Args:
            confidence_threshold: Minimum confidence (0.0-1.0) for accepting results.
                                  Default: 0.6
            use_gpu: Whether to use GPU for OCR. Default: False
            clahe_clip_limit: CLAHE contrast limit. Default: 2.0
            clahe_grid_size: CLAHE tile grid size. Default: (8, 8)

        Raises:
            ValueError: If confidence_threshold is not in [0, 1].
        """
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0 and 1, got {confidence_threshold}"
            )

        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_grid_size = clahe_grid_size

        # Lazy-loaded reader
        self._reader: Any | None = None

        log.debug(
            "jersey_ocr_initialized",
            confidence_threshold=confidence_threshold,
            use_gpu=use_gpu,
            has_easyocr=HAS_EASYOCR,
            has_cv2=HAS_CV2,
        )

    def _get_reader(self) -> Any:
        """
        Lazy-load the EasyOCR reader.

        Returns:
            EasyOCR Reader instance.

        Raises:
            ImportError: If EasyOCR is not installed.
        """
        if not HAS_EASYOCR:
            raise ImportError(
                "EasyOCR is not installed. Install with: pip install easyocr"
            )

        if self._reader is None:
            log.info("loading_easyocr_reader", use_gpu=self.use_gpu)
            self._reader = easyocr.Reader(["en"], gpu=self.use_gpu)  # type: ignore[union-attr]
            log.info("easyocr_reader_loaded")

        return self._reader

    def _load_image(self, image_or_path: str | Path | NDArray[Any]) -> NDArray[Any]:
        """
        Load image from path, PIL Image, or numpy array.

        Args:
            image_or_path: Image source (path, PIL Image, or numpy array).

        Returns:
            Image as numpy array (BGR format for OpenCV compatibility).

        Raises:
            ImageProcessingError: If image cannot be loaded.
        """
        if isinstance(image_or_path, np.ndarray):
            return image_or_path

        if isinstance(image_or_path, str | Path):
            path = Path(image_or_path)
            if not path.exists():
                raise ImageProcessingError(f"Image file not found: {path}", str(path))

            if HAS_CV2:
                img = cv2.imread(str(path))  # type: ignore[union-attr]
                if img is None:
                    raise ImageProcessingError(
                        f"Failed to load image: {path}", str(path)
                    )
                return img
            else:
                # Fallback to PIL
                try:
                    pil_img = Image.open(path)
                    return np.array(pil_img)
                except Exception as e:
                    raise ImageProcessingError(
                        f"Failed to load image with PIL: {path}: {e}", str(path)
                    ) from e

        raise ImageProcessingError(
            f"Unsupported image type: {type(image_or_path)}",
            str(image_or_path) if hasattr(image_or_path, "__str__") else None,
        )

    def _preprocess(self, image: NDArray[Any]) -> NDArray[Any]:
        """
        Preprocess image for better OCR accuracy.

        Applies CLAHE contrast enhancement and denoising to improve
        text recognition on jersey numbers.

        Args:
            image: Input image (BGR format).

        Returns:
            Preprocessed grayscale image.
        """
        if not HAS_CV2:
            log.warning("opencv_not_available_skipping_preprocessing")
            # Return grayscale without OpenCV preprocessing
            if len(image.shape) == 3:
                return np.mean(image, axis=2).astype(np.uint8)
            return image

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # type: ignore[union-attr]
        else:
            gray = image

        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(  # type: ignore[union-attr]
            clipLimit=self.clahe_clip_limit, tileGridSize=self.clahe_grid_size
        )
        enhanced = clahe.apply(gray)

        # Apply denoising
        try:
            denoised = cv2.fastNlMeansDenoising(enhanced)  # type: ignore[union-attr]
            return denoised
        except cv2.error:  # type: ignore[misc]
            # fastNlMeansDenoising may fail on small images
            log.debug("denoising_failed_using_enhanced_only")
            return enhanced

    def _is_valid_jersey_number(self, text: str) -> bool:
        """
        Check if text is a valid jersey number (1-2 digits, 0-99).

        Args:
            text: OCR recognized text.

        Returns:
            True if text is a valid jersey number.
        """
        if not text.isdigit():
            return False

        num_digits = len(text)
        if not (self.MIN_DIGITS <= num_digits <= self.MAX_DIGITS):
            return False

        # Jersey numbers are 0-99
        value = int(text)
        return 0 <= value <= 99

    def recognize(
        self, image_or_path: str | Path | NDArray[Any]
    ) -> list[tuple[str, float]]:
        """
        Recognize jersey numbers from an image.

        Performs OCR on the image and returns valid jersey numbers
        that meet the confidence threshold.

        Args:
            image_or_path: Image source (file path, PIL Image, or numpy array).

        Returns:
            List of (number, confidence) tuples sorted by confidence descending.
            Example: [("23", 0.87), ("6", 0.72)]

        Raises:
            ImportError: If EasyOCR is not installed.
            ImageProcessingError: If image cannot be processed.

        Example:
            >>> ocr = JerseyOCR()
            >>> results = ocr.recognize("./images/player.jpg")
            >>> for number, conf in results:
            ...     print(f"Jersey #{number} (confidence: {conf:.2%})")
        """
        if not HAS_EASYOCR:
            log.warning(
                "easyocr_not_installed_returning_empty",
                hint="Install with: pip install easyocr",
            )
            return []

        # Load image
        try:
            image = self._load_image(image_or_path)
        except ImageProcessingError:
            raise
        except Exception as e:
            path_str = (
                str(image_or_path) if hasattr(image_or_path, "__str__") else "array"
            )
            raise ImageProcessingError(f"Failed to load image: {e}", path_str) from e

        # Preprocess
        preprocessed = self._preprocess(image)

        # Run OCR
        reader = self._get_reader()
        try:
            raw_results = reader.readtext(preprocessed, allowlist=self.ALLOWLIST)
        except Exception as e:
            log.error("ocr_failed", error=str(e))
            raise ImageProcessingError(
                f"OCR processing failed: {e}",
                str(image_or_path) if hasattr(image_or_path, "__str__") else None,
            ) from e

        # Filter and format results
        valid_results: list[tuple[str, float]] = []

        for bbox, text, confidence in raw_results:
            text = text.strip()

            if self._is_valid_jersey_number(text):
                if confidence >= self.confidence_threshold:
                    valid_results.append((text, float(confidence)))
                    log.debug(
                        "jersey_number_found",
                        number=text,
                        confidence=confidence,
                    )
                else:
                    log.debug(
                        "jersey_number_below_threshold",
                        number=text,
                        confidence=confidence,
                        threshold=self.confidence_threshold,
                    )
            else:
                log.debug(
                    "ocr_result_rejected",
                    text=text,
                    confidence=confidence,
                    reason="not_valid_jersey_number",
                )

        # Sort by confidence descending
        valid_results.sort(key=lambda x: x[1], reverse=True)

        log.info(
            "jersey_recognition_complete",
            total_detections=len(raw_results),
            valid_numbers=len(valid_results),
            results=valid_results[:5],  # Log top 5
        )

        return valid_results

    def is_available(self) -> bool:
        """
        Check if EasyOCR is available.

        Returns:
            True if EasyOCR can be used, False otherwise.
        """
        return HAS_EASYOCR

    def __repr__(self) -> str:
        return (
            f"JerseyOCR(confidence_threshold={self.confidence_threshold}, "
            f"use_gpu={self.use_gpu}, available={self.is_available()})"
        )
