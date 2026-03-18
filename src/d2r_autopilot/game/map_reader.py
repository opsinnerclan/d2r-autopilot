"""Minimap reading and position tracking module."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import cv2
import numpy as np

from d2r_autopilot.screen.detector import ColorDetector

if TYPE_CHECKING:
    from d2r_autopilot.config import NavigationConfig
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.screen.capture import ScreenCapture

logger = logging.getLogger(__name__)

# Minimap marker colors (HSV ranges)
PLAYER_MARKER_LOWER = (0, 0, 200)
PLAYER_MARKER_UPPER = (180, 50, 255)
ENEMY_MARKER_LOWER = (0, 100, 100)
ENEMY_MARKER_UPPER = (10, 255, 255)
NPC_MARKER_LOWER = (55, 100, 100)
NPC_MARKER_UPPER = (75, 255, 255)
WAYPOINT_MARKER_LOWER = (20, 100, 100)
WAYPOINT_MARKER_UPPER = (35, 255, 255)
EXIT_MARKER_LOWER = (100, 100, 100)
EXIT_MARKER_UPPER = (130, 255, 255)


class MapReader:
    """Reads the minimap to track player position and detect landmarks."""

    def __init__(
        self,
        config: NavigationConfig,
        screen: ScreenCapture,
        state: GameState,
    ) -> None:
        self._config = config
        self._screen = screen
        self._state = state
        self._last_minimap: np.ndarray | None = None
        logger.info("MapReader initialized")

    def get_minimap_frame(self) -> np.ndarray:
        """Capture the minimap region of the screen."""
        region = self._config.minimap_region
        frame = self._screen.grab_region(region.x, region.y, region.width, region.height)
        self._last_minimap = frame
        return frame

    def find_player_position(self) -> tuple[int, int] | None:
        """Find the player's position marker on the minimap.

        Returns:
            (x, y) coordinates of player on minimap, or None if not found.
        """
        minimap = self.get_minimap_frame()
        match = ColorDetector.detect_color(minimap, PLAYER_MARKER_LOWER, PLAYER_MARKER_UPPER)
        if match.found and match.centroid is not None:
            self._state.update_position(*match.centroid)
            return match.centroid
        return None

    def find_enemies(self) -> list[tuple[int, int]]:
        """Find enemy markers on the minimap.

        Returns:
            List of (x, y) positions of enemy markers.
        """
        minimap = self.get_minimap_frame()
        hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
        lower = np.array(ENEMY_MARKER_LOWER, dtype=np.uint8)
        upper = np.array(ENEMY_MARKER_UPPER, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        positions: list[tuple[int, int]] = []
        for contour in contours:
            moments = cv2.moments(contour)
            if moments["m00"] > 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                positions.append((cx, cy))

        return positions

    def find_waypoint(self) -> tuple[int, int] | None:
        """Find the waypoint marker on the minimap.

        Returns:
            (x, y) position of waypoint, or None.
        """
        minimap = self.get_minimap_frame()
        match = ColorDetector.detect_color(minimap, WAYPOINT_MARKER_LOWER, WAYPOINT_MARKER_UPPER)
        if match.found and match.centroid is not None:
            return match.centroid
        return None

    def find_exit(self) -> tuple[int, int] | None:
        """Find the area exit/entrance on the minimap.

        Returns:
            (x, y) position of exit, or None.
        """
        minimap = self.get_minimap_frame()
        match = ColorDetector.detect_color(minimap, EXIT_MARKER_LOWER, EXIT_MARKER_UPPER)
        if match.found and match.centroid is not None:
            return match.centroid
        return None

    def get_direction_to(self, target: tuple[int, int]) -> float:
        """Calculate direction angle from player to target on minimap.

        Args:
            target: Target (x, y) on minimap.

        Returns:
            Angle in degrees (0=right, 90=down).
        """
        player = self.find_player_position()
        if player is None:
            return 0.0
        dx = target[0] - player[0]
        dy = target[1] - player[1]
        return math.degrees(math.atan2(dy, dx))

    def get_distance_to(self, target: tuple[int, int]) -> float:
        """Calculate pixel distance from player to target on minimap.

        Args:
            target: Target (x, y) on minimap.

        Returns:
            Distance in minimap pixels.
        """
        player = self.find_player_position()
        if player is None:
            return float("inf")
        dx = target[0] - player[0]
        dy = target[1] - player[1]
        return math.sqrt(dx * dx + dy * dy)

    def has_enemies_nearby(self, radius: int = 50) -> bool:
        """Check if there are enemies within a certain radius on minimap.

        Args:
            radius: Detection radius in minimap pixels.

        Returns:
            True if enemies are nearby.
        """
        enemies = self.find_enemies()
        player = self.find_player_position()
        if player is None:
            return False

        for enemy in enemies:
            dx = enemy[0] - player[0]
            dy = enemy[1] - player[1]
            if math.sqrt(dx * dx + dy * dy) <= radius:
                return True
        return False
