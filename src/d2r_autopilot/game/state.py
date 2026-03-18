"""Game state tracking and management."""

from __future__ import annotations

import logging
import time
from enum import Enum, auto

logger = logging.getLogger(__name__)


class GameScreen(Enum):
    """Possible game screens/states."""

    UNKNOWN = auto()
    MAIN_MENU = auto()
    CHARACTER_SELECT = auto()
    LOBBY = auto()
    LOADING = auto()
    IN_GAME = auto()
    INVENTORY_OPEN = auto()
    STASH_OPEN = auto()
    WAYPOINT_OPEN = auto()
    SKILL_TREE_OPEN = auto()
    NPC_DIALOG = auto()
    DEAD = auto()
    PAUSED = auto()


class Location(Enum):
    """Known game locations."""

    UNKNOWN = auto()
    # Act 1
    ROGUE_ENCAMPMENT = auto()
    BLOOD_MOOR = auto()
    DEN_OF_EVIL = auto()
    COLD_PLAINS = auto()
    # Act 2
    LUT_GHOLEIN = auto()
    ARCANE_SANCTUARY = auto()
    CANYON_OF_MAGI = auto()
    TAL_RASHAS_TOMB = auto()
    # Act 3
    KURAST_DOCKS = auto()
    TRAVINCAL = auto()
    DURANCE_OF_HATE_1 = auto()
    DURANCE_OF_HATE_2 = auto()
    DURANCE_OF_HATE_3 = auto()
    # Act 4
    PANDEMONIUM_FORTRESS = auto()
    CHAOS_SANCTUARY = auto()
    RIVER_OF_FLAME = auto()
    # Act 5
    HARROGATH = auto()
    FRIGID_HIGHLANDS = auto()
    WORLDSTONE_KEEP_1 = auto()
    WORLDSTONE_KEEP_2 = auto()
    WORLDSTONE_KEEP_3 = auto()
    THRONE_OF_DESTRUCTION = auto()


class GameState:
    """Tracks the current state of the game."""

    def __init__(self) -> None:
        self.screen: GameScreen = GameScreen.UNKNOWN
        self.location: Location = Location.UNKNOWN
        self.health_pct: float = 1.0
        self.mana_pct: float = 1.0
        self.merc_alive: bool = True
        self.is_moving: bool = False
        self.is_casting: bool = False
        self.last_position: tuple[int, int] = (0, 0)
        self.current_position: tuple[int, int] = (0, 0)
        self.game_count: int = 0
        self.run_start_time: float = 0.0
        self.deaths: int = 0
        self.items_picked: int = 0
        self._last_update: float = time.time()
        self._stuck_start: float = 0.0
        logger.info("GameState initialized")

    @property
    def in_game(self) -> bool:
        """Whether the player is currently in a game."""
        return self.screen in (
            GameScreen.IN_GAME,
            GameScreen.INVENTORY_OPEN,
            GameScreen.STASH_OPEN,
            GameScreen.WAYPOINT_OPEN,
            GameScreen.NPC_DIALOG,
        )

    @property
    def in_town(self) -> bool:
        """Whether the player is in a town area."""
        return self.location in (
            Location.ROGUE_ENCAMPMENT,
            Location.LUT_GHOLEIN,
            Location.KURAST_DOCKS,
            Location.PANDEMONIUM_FORTRESS,
            Location.HARROGATH,
        )

    @property
    def is_dead(self) -> bool:
        """Whether the player is dead."""
        return self.screen == GameScreen.DEAD

    @property
    def is_low_health(self) -> bool:
        """Whether health is critically low."""
        return self.health_pct < 0.3

    @property
    def is_low_mana(self) -> bool:
        """Whether mana is low."""
        return self.mana_pct < 0.2

    @property
    def game_elapsed(self) -> float:
        """Seconds since the current game started."""
        if self.run_start_time == 0.0:
            return 0.0
        return time.time() - self.run_start_time

    @property
    def is_stuck(self) -> bool:
        """Whether the character appears stuck (no position change)."""
        if self._stuck_start == 0.0:
            return False
        return (time.time() - self._stuck_start) > 5.0

    def update_position(self, x: int, y: int) -> None:
        """Update the character's position.

        Args:
            x: X coordinate on minimap.
            y: Y coordinate on minimap.
        """
        self.last_position = self.current_position
        self.current_position = (x, y)

        if self.last_position == self.current_position:
            if self._stuck_start == 0.0:
                self._stuck_start = time.time()
        else:
            self._stuck_start = 0.0

        self._last_update = time.time()

    def start_new_game(self) -> None:
        """Reset state for a new game."""
        self.game_count += 1
        self.run_start_time = time.time()
        self.screen = GameScreen.LOADING
        self.location = Location.UNKNOWN
        self.is_moving = False
        self.is_casting = False
        self._stuck_start = 0.0
        logger.info("New game started (run #%d)", self.game_count)

    def on_death(self) -> None:
        """Handle player death."""
        self.screen = GameScreen.DEAD
        self.deaths += 1
        logger.warning("Player died (total deaths: %d)", self.deaths)

    def get_stats(self) -> dict[str, int | float]:
        """Get current session statistics."""
        return {
            "games": self.game_count,
            "deaths": self.deaths,
            "items_picked": self.items_picked,
            "health_pct": self.health_pct,
            "mana_pct": self.mana_pct,
        }
