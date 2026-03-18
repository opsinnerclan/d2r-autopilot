"""Pathfinding and movement module."""

from __future__ import annotations

import logging
import math
import random
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.config import NavigationConfig
    from d2r_autopilot.game.map_reader import MapReader
    from d2r_autopilot.game.skills import SkillManager
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.mouse import MouseController

logger = logging.getLogger(__name__)


class MovementMode(Enum):
    """Movement mode for the pathfinder."""

    WALK = auto()
    RUN = auto()
    TELEPORT = auto()


class Pathfinder:
    """Handles character movement and navigation between areas."""

    def __init__(
        self,
        config: NavigationConfig,
        map_reader: MapReader,
        skill_manager: SkillManager,
        mouse: MouseController,
        state: GameState,
    ) -> None:
        self._config = config
        self._map = map_reader
        self._skills = skill_manager
        self._mouse = mouse
        self._state = state
        self._movement_mode = MovementMode.TELEPORT if config.teleport_enabled else MovementMode.RUN
        self._stuck_counter: int = 0
        self._max_stuck_attempts: int = 5
        logger.info("Pathfinder initialized (mode=%s)", self._movement_mode.name)

    def move_to_screen(self, target_x: int, target_y: int) -> bool:
        """Move character toward a screen coordinate.

        Args:
            target_x: Screen X position to move toward.
            target_y: Screen Y position to move toward.

        Returns:
            True if movement was successful.
        """
        if self._movement_mode == MovementMode.TELEPORT:
            self._skills.teleport(target_x, target_y)
            time.sleep(0.2)
        else:
            self._mouse.click(target_x, target_y)
            time.sleep(0.3)

        # Check if we moved
        if self._state.is_stuck:
            self._handle_stuck()
            return False

        self._stuck_counter = 0
        return True

    def move_toward_minimap(self, minimap_x: int, minimap_y: int) -> bool:
        """Move toward a position shown on the minimap.

        Converts minimap coordinates to screen coordinates and moves.

        Args:
            minimap_x: Minimap X coordinate.
            minimap_y: Minimap Y coordinate.

        Returns:
            True if movement was initiated.
        """
        # Convert minimap offset to screen direction
        player_pos = self._map.find_player_position()
        if player_pos is None:
            logger.warning("Cannot find player position on minimap")
            return False

        dx = minimap_x - player_pos[0]
        dy = minimap_y - player_pos[1]

        # Scale minimap offset to screen movement
        scale = 3.0  # Approximate scale factor
        screen_x = 960 + int(dx * scale)
        screen_y = 540 + int(dy * scale)

        # Clamp to screen bounds
        screen_x = max(100, min(screen_x, 1820))
        screen_y = max(100, min(screen_y, 980))

        return self.move_to_screen(screen_x, screen_y)

    def move_in_direction(self, angle_degrees: float, distance: int | None = None) -> bool:
        """Move the character in a compass direction.

        Args:
            angle_degrees: Direction (0=right, 90=down, 180=left, 270=up).
            distance: Pixel distance from center. Defaults to teleport_distance.

        Returns:
            True if movement was successful.
        """
        if distance is None:
            distance = self._config.teleport_distance

        rad = math.radians(angle_degrees)
        target_x = 960 + int(distance * math.cos(rad))
        target_y = 540 + int(distance * math.sin(rad))

        return self.move_to_screen(target_x, target_y)

    def navigate_to_exit(self) -> bool:
        """Navigate toward the detected area exit.

        Returns:
            True if an exit was found and movement was initiated.
        """
        exit_pos = self._map.find_exit()
        if exit_pos is None:
            logger.debug("No exit found on minimap")
            return False

        return self.move_toward_minimap(*exit_pos)

    def navigate_to_waypoint(self) -> bool:
        """Navigate toward the detected waypoint.

        Returns:
            True if a waypoint was found and movement was initiated.
        """
        wp_pos = self._map.find_waypoint()
        if wp_pos is None:
            logger.debug("No waypoint found on minimap")
            return False

        return self.move_toward_minimap(*wp_pos)

    def explore(self) -> None:
        """Move in a semi-random direction for area exploration.

        Uses a spiral-like pattern to cover the map.
        """
        angle = random.uniform(0, 360)
        distance = random.randint(200, self._config.teleport_distance)
        self.move_in_direction(angle, distance)
        time.sleep(0.3)

    def _handle_stuck(self) -> None:
        """Handle the character being stuck."""
        self._stuck_counter += 1
        logger.warning(
            "Character stuck (attempt %d/%d)",
            self._stuck_counter, self._max_stuck_attempts,
        )

        if self._stuck_counter >= self._max_stuck_attempts:
            logger.error("Max stuck attempts reached, trying random movement")
            self._stuck_counter = 0
            # Try moving in a random direction
            angle = random.uniform(0, 360)
            self.move_in_direction(angle, 150)
            time.sleep(0.5)
        else:
            # Try slight offset
            offset_x = random.randint(-100, 100)
            offset_y = random.randint(-100, 100)
            self.move_to_screen(960 + offset_x, 540 + offset_y)
            time.sleep(0.3)

    def is_near(self, target: tuple[int, int], threshold: int = 30) -> bool:
        """Check if the player is near a minimap coordinate.

        Args:
            target: (x, y) minimap coordinates.
            threshold: Distance threshold in minimap pixels.

        Returns:
            True if player is within threshold.
        """
        distance = self._map.get_distance_to(target)
        return distance <= threshold
