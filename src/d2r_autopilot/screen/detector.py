"""Template matching and object detection using OpenCV."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a template match."""

    found: bool
    confidence: float
    center_x: int
    center_y: int
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]


@dataclass
class ColorMatch:
    """Result of a color-based detection."""

    found: bool
    pixel_count: int
    percentage: float
    centroid: tuple[int, int] | None


class TemplateDetector:
    """Detects game elements using OpenCV template matching."""

    def __init__(self, threshold: float = 0.8) -> None:
        self._threshold = threshold
        self._template_cache: dict[str, np.ndarray] = {}
        logger.info("TemplateDetector initialized (threshold=%.2f)", threshold)

    def load_template(self, name: str, path: Path) -> None:
        """Load and cache a template image.

        Args:
            name: Identifier for the template.
            path: Path to the template image file.
        """
        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            logger.error("Failed to load template: %s", path)
            return
        self._template_cache[name] = template
        logger.debug("Loaded template '%s' from %s (%dx%d)", name, path, *template.shape[:2])

    def match_template(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float | None = None,
    ) -> MatchResult:
        """Find a template in the given frame.

        Args:
            frame: BGR image to search in.
            template_name: Name of a previously loaded template.
            threshold: Override detection threshold.

        Returns:
            MatchResult with detection details.
        """
        if template_name not in self._template_cache:
            logger.warning("Template '%s' not found in cache", template_name)
            return MatchResult(
                found=False, confidence=0.0, center_x=0, center_y=0,
                top_left=(0, 0), bottom_right=(0, 0),
            )

        template = self._template_cache[template_name]
        thresh = threshold if threshold is not None else self._threshold

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        h, w = template.shape[:2]
        top_left = max_loc
        bottom_right = (top_left[0] + w, top_left[1] + h)
        center_x = top_left[0] + w // 2
        center_y = top_left[1] + h // 2

        return MatchResult(
            found=max_val >= thresh,
            confidence=float(max_val),
            center_x=center_x,
            center_y=center_y,
            top_left=top_left,
            bottom_right=bottom_right,
        )

    def match_template_multi(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float | None = None,
        max_matches: int = 50,
    ) -> list[MatchResult]:
        """Find all occurrences of a template in the frame.

        Args:
            frame: BGR image to search in.
            template_name: Name of a previously loaded template.
            threshold: Override detection threshold.
            max_matches: Maximum number of matches to return.

        Returns:
            List of MatchResult objects.
        """
        if template_name not in self._template_cache:
            return []

        template = self._template_cache[template_name]
        thresh = threshold if threshold is not None else self._threshold

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= thresh)

        h, w = template.shape[:2]
        matches: list[MatchResult] = []

        for pt_y, pt_x in zip(*locations):
            matches.append(MatchResult(
                found=True,
                confidence=float(result[pt_y, pt_x]),
                center_x=int(pt_x) + w // 2,
                center_y=int(pt_y) + h // 2,
                top_left=(int(pt_x), int(pt_y)),
                bottom_right=(int(pt_x) + w, int(pt_y) + h),
            ))

        # Sort by confidence descending, limit results
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:max_matches]

    def match_raw_template(
        self,
        frame: np.ndarray,
        template: np.ndarray,
        threshold: float | None = None,
    ) -> MatchResult:
        """Match a raw template array against a frame.

        Args:
            frame: BGR image to search in.
            template: BGR template image array.
            threshold: Override detection threshold.

        Returns:
            MatchResult with detection details.
        """
        thresh = threshold if threshold is not None else self._threshold

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        h, w = template.shape[:2]
        top_left = max_loc
        bottom_right = (top_left[0] + w, top_left[1] + h)
        center_x = top_left[0] + w // 2
        center_y = top_left[1] + h // 2

        return MatchResult(
            found=max_val >= thresh,
            confidence=float(max_val),
            center_x=center_x,
            center_y=center_y,
            top_left=top_left,
            bottom_right=bottom_right,
        )


class ColorDetector:
    """Detects game elements by color in HSV space."""

    @staticmethod
    def detect_color(
        frame: np.ndarray,
        lower_hsv: tuple[int, int, int],
        upper_hsv: tuple[int, int, int],
    ) -> ColorMatch:
        """Detect pixels within a color range.

        Args:
            frame: BGR image.
            lower_hsv: Lower HSV bound.
            upper_hsv: Upper HSV bound.

        Returns:
            ColorMatch with detection results.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array(lower_hsv, dtype=np.uint8)
        upper = np.array(upper_hsv, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        pixel_count = int(cv2.countNonZero(mask))
        total_pixels = mask.shape[0] * mask.shape[1]
        percentage = pixel_count / total_pixels if total_pixels > 0 else 0.0

        centroid: tuple[int, int] | None = None
        if pixel_count > 0:
            moments = cv2.moments(mask)
            if moments["m00"] > 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                centroid = (cx, cy)

        return ColorMatch(
            found=pixel_count > 0,
            pixel_count=pixel_count,
            percentage=percentage,
            centroid=centroid,
        )

    @staticmethod
    def get_dominant_color(frame: np.ndarray, k: int = 3) -> list[tuple[int, int, int]]:
        """Find dominant colors using k-means clustering.

        Args:
            frame: BGR image.
            k: Number of clusters.

        Returns:
            List of dominant BGR color tuples.
        """
        pixels = frame.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

        return [(int(c[0]), int(c[1]), int(c[2])) for c in centers]

    @staticmethod
    def color_ratio_in_region(
        frame: np.ndarray,
        lower_hsv: tuple[int, int, int],
        upper_hsv: tuple[int, int, int],
    ) -> float:
        """Calculate the ratio of matching pixels in a region.

        Args:
            frame: BGR image of the region.
            lower_hsv: Lower HSV bound.
            upper_hsv: Upper HSV bound.

        Returns:
            Float ratio [0.0, 1.0] of matching pixels.
        """
        match = ColorDetector.detect_color(frame, lower_hsv, upper_hsv)
        return match.percentage
