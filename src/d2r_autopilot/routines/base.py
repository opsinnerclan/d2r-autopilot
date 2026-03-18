"""Base farming routine class."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.combat.engine import CombatEngine
    from d2r_autopilot.config import RoutineConfig
    from d2r_autopilot.game.health import HealthMonitor
    from d2r_autopilot.game.map_reader import MapReader
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.loot.picker import LootPicker
    from d2r_autopilot.navigation.pathfinder import Pathfinder
    from d2r_autopilot.navigation.town import TownNavigator

logger = logging.getLogger(__name__)


class RoutinePhase(Enum):
    """Phases of a farming routine."""

    INIT = auto()
    TOWN_PREP = auto()
    NAVIGATE = auto()
    CLEAR = auto()
    BOSS_FIGHT = auto()
    LOOT = auto()
    RETURN_TOWN = auto()
    COMPLETE = auto()
    FAILED = auto()


class BaseRoutine(ABC):
    """Abstract base class for farming routines.

    Subclasses implement specific boss runs or farming paths.
    """

    def __init__(
        self,
        config: RoutineConfig,
        state: GameState,
        combat: CombatEngine,
        pathfinder: Pathfinder,
        town: TownNavigator,
        map_reader: MapReader,
        health: HealthMonitor,
        loot_picker: LootPicker,
    ) -> None:
        self._config = config
        self._state = state
        self._combat = combat
        self._path = pathfinder
        self._town = town
        self._map = map_reader
        self._health = health
        self._loot = loot_picker
        self._phase = RoutinePhase.INIT
        self._start_time: float = 0.0
        self._run_count: int = 0

    @property
    def name(self) -> str:
        """Name of this routine."""
        return self.__class__.__name__

    @property
    def phase(self) -> RoutinePhase:
        return self._phase

    @property
    def elapsed(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.time() - self._start_time

    def run(self) -> bool:
        """Execute one full run of the routine.

        Returns:
            True if the run completed successfully.
        """
        self._start_time = time.time()
        self._run_count += 1
        logger.info("Starting %s run #%d", self.name, self._run_count)

        try:
            # Phase 1: Town preparation
            self._phase = RoutinePhase.TOWN_PREP
            self.town_prep()

            # Phase 2: Navigate to farming area
            self._phase = RoutinePhase.NAVIGATE
            if not self.navigate():
                logger.warning("Navigation failed in %s", self.name)
                self._phase = RoutinePhase.FAILED
                return False

            # Phase 3: Clear area / kill boss
            self._phase = RoutinePhase.CLEAR
            self.clear()

            # Phase 4: Boss fight (if applicable)
            self._phase = RoutinePhase.BOSS_FIGHT
            self.boss_fight()

            # Phase 5: Loot
            self._phase = RoutinePhase.LOOT
            self.loot()

            # Phase 6: Return to town
            self._phase = RoutinePhase.RETURN_TOWN
            self.return_to_town()

            self._phase = RoutinePhase.COMPLETE
            elapsed = self.elapsed
            logger.info(
                "%s run #%d complete in %.1fs",
                self.name, self._run_count, elapsed,
            )
            return True

        except Exception:
            logger.exception("Error during %s run #%d", self.name, self._run_count)
            self._phase = RoutinePhase.FAILED
            return False

    @abstractmethod
    def town_prep(self) -> None:
        """Prepare in town before the run (repair, buy potions, etc)."""
        ...

    @abstractmethod
    def navigate(self) -> bool:
        """Navigate from town to the farming area.

        Returns:
            True if navigation was successful.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear enemies in the farming area."""
        ...

    @abstractmethod
    def boss_fight(self) -> None:
        """Fight the boss (if applicable)."""
        ...

    def loot(self) -> None:
        """Pick up loot after clearing."""
        self._loot.scan_and_pickup()

    def return_to_town(self) -> None:
        """Return to town after the run."""

        # Default: cast TP and click it
        logger.info("Returning to town via Town Portal")
        # This will be handled by the skill manager through the bot

    def check_timeout(self) -> bool:
        """Check if the run has exceeded max time.

        Returns:
            True if timeout reached.
        """
        if self._config.max_game_time > 0 and self.elapsed > self._config.max_game_time:
            logger.warning("Run timeout reached (%.0fs)", self.elapsed)
            return True
        return False

    def check_chicken(self) -> bool:
        """Check if we need to chicken (emergency exit).

        Returns:
            True if chicken is needed.
        """
        if self._state.is_dead:
            logger.warning("Player is dead, ending run")
            return True
        if self._state.health_pct < 0.1 and self._config.chicken_on_death:
            logger.warning("Health critical, chickening")
            return True
        return False
