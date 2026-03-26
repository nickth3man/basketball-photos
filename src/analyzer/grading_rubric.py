import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.types.config import WeightsConfig
from src.types.errors import ImageReadError
from src.types.scores import PhotoScore

logger = logging.getLogger(__name__)

try:
    from scipy import ndimage as scipy_ndimage

    SCIPY_AVAILABLE = True
except ImportError:
    scipy_ndimage = None
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available, using numpy-only fallbacks for analysis")


class GradingRubric:
    """10-parameter grading rubric for photo quality assessment.

    Uses only Pillow, numpy, and scipy (when available) for analysis.
    No OpenCV or scikit-image required.
    """

    SCORE_MIN = 1.0
    SCORE_MAX = 10.0

    def __init__(self, weights: WeightsConfig | dict[str, float] | None = None):
        if weights is None:
            self.weights = WeightsConfig()
        elif isinstance(weights, WeightsConfig):
            self.weights = weights
        else:
            self.weights = WeightsConfig(**weights)

    def score_image(
        self, image_path: str | Path, context_text: str | None = None
    ) -> PhotoScore:
        image_path = Path(image_path)

        try:
            with Image.open(image_path) as img:
                img.load()

                img_array = np.array(img.convert("RGB"), dtype=np.float64)
                gray_array = np.array(img.convert("L"), dtype=np.float64)

                scores = {
                    "resolution_clarity": self._score_resolution_clarity(
                        img, gray_array
                    ),
                    "composition": self._score_composition(img, gray_array, img_array),
                    "action_moment": self._score_action_moment(gray_array, img_array),
                    "lighting": self._score_lighting(gray_array),
                    "color_quality": self._score_color_quality(img_array),
                    "subject_isolation": self._score_subject_isolation(
                        gray_array, img_array
                    ),
                    "emotional_impact": self._score_emotional_impact(
                        img_array, gray_array
                    ),
                    "technical_quality": self._score_technical_quality(gray_array, img),
                    "relevance": self._score_relevance(context_text),
                    "instagram_suitability": self._score_instagram_suitability(img),
                }

                return PhotoScore(
                    resolution_clarity=scores["resolution_clarity"],
                    composition=scores["composition"],
                    action_moment=scores["action_moment"],
                    lighting=scores["lighting"],
                    color_quality=scores["color_quality"],
                    subject_isolation=scores["subject_isolation"],
                    emotional_impact=scores["emotional_impact"],
                    technical_quality=scores["technical_quality"],
                    relevance=scores["relevance"],
                    instagram_suitability=scores["instagram_suitability"],
                    weights=self.weights.to_dict(),
                )

        except Exception as e:
            raise ImageReadError(f"Failed to analyze image: {e}", str(image_path))

    def _clamp_score(self, score: float | np.floating[Any]) -> float:
        return float(max(self.SCORE_MIN, min(self.SCORE_MAX, round(float(score), 1))))

    def _score_resolution_clarity(
        self, img: Image.Image, gray_array: np.ndarray
    ) -> float:
        width, height = img.size
        megapixels = (width * height) / 1_000_000

        mp_score = min(10.0, megapixels / 1.2)

        if SCIPY_AVAILABLE and scipy_ndimage is not None:
            laplacian = scipy_ndimage.laplace(gray_array)
            blur_variance = float(laplacian.var())
        else:
            gx = np.abs(np.diff(gray_array, axis=0, prepend=0))
            gy = np.abs(np.diff(gray_array, axis=1, prepend=0))
            edge_variance = float((gx.var() + gy.var()) / 2)
            blur_variance = edge_variance

        sharpness_score = min(10.0, blur_variance / 500.0)

        score = (mp_score * 0.4) + (sharpness_score * 0.6)
        return self._clamp_score(score)

    def _score_composition(
        self, img: Image.Image, gray_array: np.ndarray, rgb_array: np.ndarray
    ) -> float:
        width, height = img.size

        if SCIPY_AVAILABLE and scipy_ndimage is not None:
            edges = scipy_ndimage.sobel(gray_array)
        else:
            gx = np.abs(np.diff(gray_array, axis=1, prepend=0))
            gy = np.abs(np.diff(gray_array, axis=0, prepend=0))
            edges = np.sqrt(gx**2 + gy**2)

        edge_density = float(np.mean(edges > np.percentile(edges, 90)))

        third_h, third_w = height // 3, width // 3
        power_points = [
            (third_h, third_w),
            (third_h, 2 * third_w),
            (2 * third_h, third_w),
            (2 * third_h, 2 * third_w),
        ]

        roi_size = min(third_h, third_w) // 2
        power_point_scores = []

        for py, px in power_points:
            y_start = max(0, py - roi_size)
            y_end = min(height, py + roi_size)
            x_start = max(0, px - roi_size)
            x_end = min(width, px + roi_size)

            roi = edges[y_start:y_end, x_start:x_end]
            if roi.size > 0:
                power_point_scores.append(float(np.mean(roi)))

        avg_edges = float(np.mean(edges)) + 1e-10
        rule_of_thirds = min(1.0, np.mean(power_point_scores) / avg_edges)

        score = 5.0 + (edge_density * 3) + (rule_of_thirds * 2)
        return self._clamp_score(score)

    def _score_action_moment(
        self, gray_array: np.ndarray, rgb_array: np.ndarray
    ) -> float:
        if SCIPY_AVAILABLE and scipy_ndimage is not None:
            edges = scipy_ndimage.sobel(gray_array)
        else:
            gx = np.abs(np.diff(gray_array, axis=1, prepend=0))
            gy = np.abs(np.diff(gray_array, axis=0, prepend=0))
            edges = np.sqrt(gx**2 + gy**2)

        edge_density = float(np.mean(np.abs(edges))) / 255.0

        local_std = float(np.std(gray_array))
        contrast_energy = local_std / 128.0

        gradient_x = np.diff(gray_array, axis=1, prepend=0)
        gradient_y = np.diff(gray_array, axis=0, prepend=0)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        motion_score = float(np.percentile(gradient_magnitude, 95)) / 255.0

        score = 3.0 + (edge_density * 3) + (contrast_energy * 2) + (motion_score * 2)
        return self._clamp_score(score)

    def _score_lighting(self, gray_array: np.ndarray) -> float:
        mean_brightness = float(np.mean(gray_array))

        if mean_brightness < 50:
            exposure_score = mean_brightness / 50.0 * 5.0
        elif mean_brightness > 200:
            exposure_score = (255.0 - mean_brightness) / 55.0 * 5.0
        else:
            exposure_score = 10.0

        rms_contrast = float(np.std(gray_array))
        contrast_score = min(10.0, rms_contrast / 25.0)

        hist, _ = np.histogram(gray_array, bins=256, range=(0, 256))
        hist_norm = hist / gray_array.size

        non_zero = hist_norm[hist_norm > 0]
        if len(non_zero) > 0:
            entropy = float(-np.sum(non_zero * np.log2(non_zero + 1e-10)))
            dynamic_range_score = min(10.0, entropy / 5.0)
        else:
            dynamic_range_score = 5.0

        score = (
            (exposure_score * 0.4)
            + (contrast_score * 0.4)
            + (dynamic_range_score * 0.2)
        )
        return self._clamp_score(score)

    def _score_color_quality(self, rgb_array: np.ndarray) -> float:
        r, g, b = rgb_array[:, :, 0], rgb_array[:, :, 1], rgb_array[:, :, 2]

        max_rgb = np.maximum(np.maximum(r, g), b)
        min_rgb = np.minimum(np.minimum(r, g), b)

        with np.errstate(divide="ignore", invalid="ignore"):
            saturation = np.where(max_rgb > 0, (max_rgb - min_rgb) / max_rgb, 0)
            saturation = np.nan_to_num(saturation)

        avg_saturation = float(np.mean(saturation))
        saturation_score = min(10.0, avg_saturation * 15.0)

        color_variance = float(np.std([np.mean(r), np.mean(g), np.mean(b)]))
        balance_score = max(0.0, 10.0 - color_variance / 10.0)

        r_std, g_std, b_std = float(np.std(r)), float(np.std(g)), float(np.std(b))
        vibrancy = (r_std + g_std + b_std) / 3.0 / 128.0
        vibrancy_score = min(10.0, vibrancy * 10.0)

        score = (
            (saturation_score * 0.5) + (balance_score * 0.25) + (vibrancy_score * 0.25)
        )
        return self._clamp_score(score)

    def _score_subject_isolation(
        self, gray_array: np.ndarray, rgb_array: np.ndarray
    ) -> float:
        if SCIPY_AVAILABLE and scipy_ndimage is not None:
            edges = scipy_ndimage.sobel(gray_array)
        else:
            gx = np.abs(np.diff(gray_array, axis=1, prepend=0))
            gy = np.abs(np.diff(gray_array, axis=0, prepend=0))
            edges = np.sqrt(gx**2 + gy**2)

        edge_magnitude = np.abs(edges)

        threshold = float(np.percentile(edge_magnitude, 75))
        high_edge_mask = edge_magnitude > threshold

        center_y, center_x = gray_array.shape[0] // 2, gray_array.shape[1] // 2
        radius = min(center_y, center_x)

        y_coords, x_coords = np.ogrid[: gray_array.shape[0], : gray_array.shape[1]]
        distance_from_center = np.sqrt(
            (y_coords - center_y) ** 2 + (x_coords - center_x) ** 2
        )
        center_mask = distance_from_center <= radius

        center_edges = int(np.sum(high_edge_mask & center_mask))
        total_edges = int(np.sum(high_edge_mask)) + 1
        center_concentration = center_edges / total_edges

        hist, _ = np.histogram(gray_array, bins=32)
        hist_norm = hist / gray_array.size
        background_simplicity = (
            1.0 - float(np.sum(hist_norm * np.log2(hist_norm + 1e-10))) / 5.0
        )

        score = 3.0 + (center_concentration * 4) + (background_simplicity * 3)
        return self._clamp_score(score)

    def _score_emotional_impact(
        self, rgb_array: np.ndarray, gray_array: np.ndarray
    ) -> float:
        r, g, b = rgb_array[:, :, 0], rgb_array[:, :, 1], rgb_array[:, :, 2]

        warmth = float(np.mean(r)) - float(np.mean(b))
        warmth_score = min(10.0, max(0.0, (warmth / 25.5) * 5.0 + 5.0))

        contrast = float(np.std(gray_array))
        contrast_score = min(10.0, contrast / 25.0)

        r_range = float(np.max(r)) - float(np.min(r))
        g_range = float(np.max(g)) - float(np.min(g))
        b_range = float(np.max(b)) - float(np.min(b))
        color_range = (r_range + g_range + b_range) / 3.0
        drama_score = min(10.0, color_range / 25.0)

        score = (warmth_score * 0.3) + (contrast_score * 0.4) + (drama_score * 0.3)
        return self._clamp_score(score)

    def _score_technical_quality(
        self, gray_array: np.ndarray, img: Image.Image
    ) -> float:
        height, width = gray_array.shape
        block_size = 8

        trimmed_h = (height // block_size) * block_size
        trimmed_w = (width // block_size) * block_size

        if trimmed_h < block_size or trimmed_w < block_size:
            return 5.0

        trimmed = gray_array[:trimmed_h, :trimmed_w]

        blocks = trimmed.reshape(
            trimmed_h // block_size,
            block_size,
            trimmed_w // block_size,
            block_size,
        )
        blocks = blocks.transpose(0, 2, 1, 3).reshape(-1, block_size * block_size)

        local_stds = np.std(blocks, axis=1)
        noise_estimate = float(np.median(local_stds))
        noise_score = max(0.0, 10.0 - noise_estimate / 10.0)

        width, height = img.size
        file_size_estimate = width * height * 3
        actual_size = len(img.tobytes())

        if actual_size > 0:
            compression_ratio = file_size_estimate / actual_size
            compression_score = min(10.0, max(1.0, 10.0 - compression_ratio / 3.0))
        else:
            compression_score = 5.0

        score = (noise_score * 0.6) + (compression_score * 0.4)
        return self._clamp_score(score)

    def _score_relevance(self, context_text: str | None = None) -> float:
        if not context_text:
            return 5.0

        normalized = context_text.lower()
        strong_matches = [
            "basketball",
            "nba",
            "wnba",
            "olympic",
            "playoffs",
            "finals",
            "championship",
            "dunk",
            "three",
            "portrait",
            "celebration",
            "game",
            "court",
            "player",
        ]
        niche_matches = [
            "vintage",
            "historic",
            "iconic",
            "arena",
            "hoop",
            "sports",
            "athlete",
        ]

        score = 4.0
        score += min(
            4.0, sum(1 for keyword in strong_matches if keyword in normalized) * 0.5
        )
        score += min(
            2.0, sum(1 for keyword in niche_matches if keyword in normalized) * 0.25
        )
        return self._clamp_score(score)

    def _score_instagram_suitability(self, img: Image.Image) -> float:
        width, height = img.size
        aspect_ratio = width / height if height > 0 else 1.0

        if 0.95 <= aspect_ratio <= 1.05:
            aspect_score = 10.0
        elif 0.8 <= aspect_ratio <= 1.25:
            aspect_score = 8.0
        elif 0.5 <= aspect_ratio <= 2.0:
            aspect_score = 6.0
        else:
            aspect_score = 3.0

        min_dimension = min(width, height)
        if min_dimension >= 1350:
            resolution_score = 10.0
        elif min_dimension >= 1080:
            resolution_score = 8.0
        elif min_dimension >= 720:
            resolution_score = 6.0
        elif min_dimension >= 480:
            resolution_score = 4.0
        else:
            resolution_score = 2.0

        score = (aspect_score * 0.5) + (resolution_score * 0.5)
        return self._clamp_score(score)
