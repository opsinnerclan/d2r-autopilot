"""Screen capture module using mss for fast screenshot acquisition."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import mss
import numpy as np

if TYPE_CHECKING:
    from d2r_autopilot.config import ScreenConfig, ScreenRegion

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures screenshots from the game window using mss."""

    def __init__(self, config: ScreenConfig) -> None:
        self._config = config
        self._sct = mss.mss()
        self._last_capture_time: float = 0.0
        self._frame_count: int = 0
        logger.info(
            "ScreenCapture initialized (monitor=%d, region=%dx%d)",
            config.monitor_index,
            config.game_region.width,
            config.game_region.height,
        )

    @property
    def fps(self) -> float:
        """Approximate captures per second."""
        elapsed = time.time() - self._last_capture_time
        if elapsed <= 0 or self._frame_count == 0:
            return 0.0
        return self._frame_count / elapsed

    def grab_frame(self, region: ScreenRegion | None = None) -> np.ndarray:
        """Capture a single frame from the screen.

        Args:
            region: Optional sub-region to capture. Uses full game region if None.

        Returns:
            BGR numpy array of the captured frame.
        """
        if region is None:
            region = self._config.game_region

        monitor = {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }

        screenshot = self._sct.grab(monitor)
        frame: np.ndarray = np.array(screenshot, dtype=np.uint8)
        # mss returns BGRA, convert to BGR for OpenCV compatibility
        frame = frame[:, :, :3]

        self._frame_count += 1
        if self._last_capture_time == 0.0:
            self._last_capture_time = time.time()

        return frame

    def grab_region(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Capture a specific region of the screen.

        Args:
            x: Left coordinate.
            y: Top coordinate.
            width: Width of the region.
            height: Height of the region.

        Returns:
            BGR numpy array of the captured region.
        """
        from d2r_autopilot.config import ScreenRegion

        region = ScreenRegion(x=x, y=y, width=width, height=height)
        return self.grab_frame(region)

    def close(self) -> None:
        """Release screen capture resources."""
        self._sct.close()
        logger.info("ScreenCapture closed (total frames: %d)", self._frame_count)
