"""OCR module for reading text from game screenshots."""

from __future__ import annotations

import logging
import re

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pytesseract

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available, OCR features disabled")


class GameOCR:
    """Reads text from D2R game screenshots using Tesseract OCR."""

    def __init__(self, lang: str = "eng") -> None:
        self._lang = lang
        if not TESSERACT_AVAILABLE:
            logger.warning("OCR initialized but pytesseract is not installed")

    def read_text(self, frame: np.ndarray, preprocess: bool = True) -> str:
        """Read text from an image region.

        Args:
            frame: BGR image containing text.
            preprocess: Whether to apply preprocessing for better OCR.

        Returns:
            Recognized text string.
        """
        if not TESSERACT_AVAILABLE:
            return ""

        if preprocess:
            frame = self._preprocess(frame)

        text: str = pytesseract.image_to_string(frame, lang=self._lang)
        return text.strip()

    def read_item_name(self, frame: np.ndarray) -> str:
        """Read an item name from a tooltip region.

        Applies specialized preprocessing for D2R item text.

        Args:
            frame: BGR image of the item tooltip.

        Returns:
            Item name string.
        """
        if not TESSERACT_AVAILABLE:
            return ""

        processed = self._preprocess_item_text(frame)
        text: str = pytesseract.image_to_string(
            processed, lang=self._lang, config="--psm 7"
        )
        return self._clean_item_text(text.strip())

    def read_numbers(self, frame: np.ndarray) -> list[int]:
        """Extract numbers from an image region.

        Args:
            frame: BGR image containing numbers.

        Returns:
            List of integers found in the image.
        """
        if not TESSERACT_AVAILABLE:
            return []

        processed = self._preprocess(frame)
        text: str = pytesseract.image_to_string(
            processed, lang=self._lang, config="--psm 7 digits"
        )
        numbers = re.findall(r"\d+", text)
        return [int(n) for n in numbers]

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Standard preprocessing for OCR."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        scaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    @staticmethod
    def _preprocess_item_text(frame: np.ndarray) -> np.ndarray:
        """Preprocessing optimized for D2R item tooltip text."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        # Invert if text is light on dark background
        mean_val = float(np.mean(scaled))
        if mean_val < 128:
            scaled = cv2.bitwise_not(scaled)
        _, binary = cv2.threshold(scaled, 150, 255, cv2.THRESH_BINARY)
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        return binary

    @staticmethod
    def _clean_item_text(text: str) -> str:
        """Clean up OCR artifacts from item text."""
        text = re.sub(r"[^\w\s\-'+]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
