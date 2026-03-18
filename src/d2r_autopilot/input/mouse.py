"""Mouse input simulation for D2R."""

from __future__ import annotations

import logging
import math
import random
import time
from typing import TYPE_CHECKING

import pyautogui

if TYPE_CHECKING:
    from d2r_autopilot.config import InputConfig

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = False


class MouseController:
    """Simulates mouse input with human-like movement patterns."""

    def __init__(self, config: InputConfig) -> None:
        self._config = config
        self._screen_width, self._screen_height = pyautogui.size()
        logger.info(
            "MouseController initialized (screen=%dx%d)",
            self._screen_width,
            self._screen_height,
        )

    @property
    def position(self) -> tuple[int, int]:
        """Current mouse position."""
        pos = pyautogui.position()
        return (pos[0], pos[1])

    def move_to(self, x: int, y: int, duration: float | None = None) -> None:
        """Move mouse to absolute screen coordinates.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            duration: Movement duration in seconds (None for config default).
        """
        if duration is None:
            duration = self._config.mouse_move_speed

        # Add slight randomness to destination for human-like behavior
        x += random.randint(-2, 2)
        y += random.randint(-2, 2)

        # Clamp to screen bounds
        x = max(0, min(x, self._screen_width - 1))
        y = max(0, min(y, self._screen_height - 1))

        pyautogui.moveTo(x, y, duration=duration)
        logger.debug("Mouse moved to (%d, %d)", x, y)

    def move_relative(self, dx: int, dy: int, duration: float | None = None) -> None:
        """Move mouse relative to current position.

        Args:
            dx: Horizontal offset.
            dy: Vertical offset.
            duration: Movement duration.
        """
        if duration is None:
            duration = self._config.mouse_move_speed
        pyautogui.moveRel(dx, dy, duration=duration)

    def click(self, x: int | None = None, y: int | None = None) -> None:
        """Left click at the given position or current position.

        Args:
            x: X coordinate (None for current position).
            y: Y coordinate (None for current position).
        """
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(self._config.click_delay)
        pyautogui.click()
        logger.debug("Left click at %s", self.position)

    def right_click(self, x: int | None = None, y: int | None = None) -> None:
        """Right click at the given position or current position.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(self._config.click_delay)
        pyautogui.rightClick()
        logger.debug("Right click at %s", self.position)

    def click_and_hold(self, x: int, y: int, duration: float = 1.0) -> None:
        """Click and hold at a position for a duration.

        Args:
            x: X coordinate.
            y: Y coordinate.
            duration: How long to hold in seconds.
        """
        self.move_to(x, y)
        pyautogui.mouseDown()
        time.sleep(duration)
        pyautogui.mouseUp()
        logger.debug("Click and hold at (%d, %d) for %.1fs", x, y, duration)

    def move_to_center(self) -> None:
        """Move mouse to the center of the screen."""
        self.move_to(self._screen_width // 2, self._screen_height // 2)

    def move_in_direction(self, angle_degrees: float, distance: int) -> None:
        """Move the mouse in a direction from center screen.

        Args:
            angle_degrees: Direction in degrees (0=right, 90=down, 180=left, 270=up).
            distance: Pixel distance from center.
        """
        center_x = self._screen_width // 2
        center_y = self._screen_height // 2
        rad = math.radians(angle_degrees)
        target_x = center_x + int(distance * math.cos(rad))
        target_y = center_y + int(distance * math.sin(rad))
        self.move_to(target_x, target_y)

    def distance_to(self, x: int, y: int) -> float:
        """Calculate distance from current position to a point.

        Args:
            x: Target X.
            y: Target Y.

        Returns:
            Euclidean distance in pixels.
        """
        cx, cy = self.position
        return math.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    def scroll(self, clicks: int) -> None:
        """Scroll the mouse wheel.

        Args:
            clicks: Positive for up, negative for down.
        """
        pyautogui.scroll(clicks)
        logger.debug("Scroll: %d", clicks)
