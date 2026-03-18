"""Health and mana monitoring module."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from d2r_autopilot.screen.detector import ColorDetector

if TYPE_CHECKING:
    from d2r_autopilot.config import HealthBarConfig
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.keyboard import KeyboardController
    from d2r_autopilot.screen.capture import ScreenCapture

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors health/mana orbs and manages potion usage."""

    def __init__(
        self,
        config: HealthBarConfig,
        screen: ScreenCapture,
        keyboard: KeyboardController,
        state: GameState,
        potion_keys: dict[str, str],
    ) -> None:
        self._config = config
        self._screen = screen
        self._keyboard = keyboard
        self._state = state
        self._potion_keys = potion_keys
        self._last_health_potion_time: float = 0.0
        self._last_mana_potion_time: float = 0.0
        self._last_rejuv_time: float = 0.0
        self._potion_cooldown: float = 1.0
        logger.info("HealthMonitor initialized")

    def update(self) -> None:
        """Read health and mana values from screen and update game state."""
        health_pct = self._read_health()
        mana_pct = self._read_mana()

        self._state.health_pct = health_pct
        self._state.mana_pct = mana_pct

    def _read_health(self) -> float:
        """Read the health orb percentage."""
        region = self._config.health_region
        frame = self._screen.grab_region(region.x, region.y, region.width, region.height)
        return self._measure_orb_fill(
            frame,
            self._config.health_color_lower,
            self._config.health_color_upper,
        )

    def _read_mana(self) -> float:
        """Read the mana orb percentage."""
        region = self._config.mana_region
        frame = self._screen.grab_region(region.x, region.y, region.width, region.height)
        return self._measure_orb_fill(
            frame,
            self._config.mana_color_lower,
            self._config.mana_color_upper,
        )

    @staticmethod
    def _measure_orb_fill(
        frame: np.ndarray,
        lower_hsv: tuple[int, int, int],
        upper_hsv: tuple[int, int, int],
    ) -> float:
        """Measure the fill percentage of a health/mana orb.

        The orb fills from bottom to top, so we measure the ratio
        of colored pixels in the region.

        Args:
            frame: BGR image of the orb region.
            lower_hsv: Lower HSV bound for the orb color.
            upper_hsv: Upper HSV bound for the orb color.

        Returns:
            Fill percentage [0.0, 1.0].
        """
        ratio = ColorDetector.color_ratio_in_region(frame, lower_hsv, upper_hsv)
        # Clamp to valid range
        return max(0.0, min(1.0, ratio))

    def manage_potions(self) -> bool:
        """Check health/mana and use potions as needed.

        Returns:
            True if a chicken (emergency exit) is needed.
        """
        now = time.time()

        # Emergency: use rejuvenation potion
        if self._state.health_pct < self._config.chicken_threshold * 2:
            if self._can_use_rejuv(now):
                self._use_rejuv(now)
                return False

        # Chicken out if health is critically low
        if self._state.health_pct < self._config.chicken_threshold:
            logger.critical(
                "Health critical (%.0f%%), chickening!", self._state.health_pct * 100
            )
            return True

        # Use healing potion
        if self._state.health_pct < self._config.potion_threshold:
            if self._can_use_health_potion(now):
                self._use_health_potion(now)

        # Use mana potion
        if self._state.mana_pct < self._config.potion_threshold:
            if self._can_use_mana_potion(now):
                self._use_mana_potion(now)

        return False

    def _can_use_health_potion(self, now: float) -> bool:
        return (now - self._last_health_potion_time) >= self._potion_cooldown

    def _can_use_mana_potion(self, now: float) -> bool:
        return (now - self._last_mana_potion_time) >= self._potion_cooldown

    def _can_use_rejuv(self, now: float) -> bool:
        return (now - self._last_rejuv_time) >= self._potion_cooldown

    def _use_health_potion(self, now: float) -> None:
        key = self._potion_keys.get("healing", "1")
        self._keyboard.use_potion(key)
        self._last_health_potion_time = now
        logger.info("Used healing potion (health=%.0f%%)", self._state.health_pct * 100)

    def _use_mana_potion(self, now: float) -> None:
        key = self._potion_keys.get("mana", "2")
        self._keyboard.use_potion(key)
        self._last_mana_potion_time = now
        logger.info("Used mana potion (mana=%.0f%%)", self._state.mana_pct * 100)

    def _use_rejuv(self, now: float) -> None:
        key = self._potion_keys.get("rejuv", "3")
        self._keyboard.use_potion(key)
        self._last_rejuv_time = now
        logger.info("Used rejuvenation potion (health=%.0f%%)", self._state.health_pct * 100)
