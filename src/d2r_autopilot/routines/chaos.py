"""Chaos Sanctuary farming routine - Act 4 Hell."""

from __future__ import annotations

import logging
import time

from d2r_autopilot.routines.base import BaseRoutine

logger = logging.getLogger(__name__)

RIVER_OF_FLAME_WP = 3  # Act 4 waypoint list index


class ChaosRoutine(BaseRoutine):
    """Farms Chaos Sanctuary and Diablo.

    Strategy:
    1. Waypoint to River of Flame
    2. Navigate to Chaos Sanctuary entrance
    3. Clear the 3 seal areas (Vizier, De Seis, Infector)
    4. Kill Diablo
    5. Loot and return to town
    """

    @property
    def name(self) -> str:
        return "ChaosRun"

    def town_prep(self) -> None:
        """Prepare in Pandemonium Fortress."""
        logger.info("Town prep for Chaos run")
        self._town.act = 4
        should_repair = self._run_count % (self._config.repair_interval or 10) == 0
        should_stash = self._run_count % (self._config.stash_interval or 5) == 0
        self._town.do_town_routine(
            repair=should_repair,
            stash=should_stash,
            heal=True,
        )

    def navigate(self) -> bool:
        """Navigate to Chaos Sanctuary.

        Returns:
            True if successfully reached the Sanctuary.
        """
        logger.info("Navigating to Chaos Sanctuary")

        # Use River of Flame waypoint
        if not self._town.use_waypoint(RIVER_OF_FLAME_WP):
            logger.error("Failed to use River of Flame waypoint")
            return False

        time.sleep(2.0)

        # Teleport toward the Chaos Sanctuary entrance
        # The entrance is generally in a consistent direction from the waypoint
        max_teleports = 40
        for i in range(max_teleports):
            if self.check_timeout() or self.check_chicken():
                return False

            exit_pos = self._map.find_exit()
            if exit_pos is not None:
                logger.info("Found Chaos Sanctuary entrance at %s", exit_pos)
                while not self._path.is_near(exit_pos, threshold=25):
                    if self.check_timeout():
                        return False
                    self._path.move_toward_minimap(*exit_pos)
                    time.sleep(0.3)
                return True

            # Teleport in the general direction (varies per map)
            self._path.explore()

            if i % 10 == 0:
                logger.debug("Searching for CS entrance... (%d/%d)", i, max_teleports)

        logger.error("Failed to find Chaos Sanctuary entrance")
        return False

    def clear(self) -> None:
        """Clear the Chaos Sanctuary: open seals and kill seal bosses."""
        logger.info("Clearing Chaos Sanctuary")
        seal_areas = ["vizier", "de_seis", "infector"]

        for seal in seal_areas:
            logger.info("Clearing %s seal area", seal)
            self._clear_seal_area()
            time.sleep(1.0)

    def _clear_seal_area(self) -> None:
        """Clear a single seal area and activate the seal."""
        max_clear_time = 30.0
        start = time.time()

        while (time.time() - start) < max_clear_time:
            if self.check_chicken():
                return

            self._health.update()
            needs_chicken = self._health.manage_potions()
            if needs_chicken:
                return

            enemies = self._map.find_enemies()
            if not enemies:
                break

            screen_enemies = [
                (960 + (ex - 130) * 3, 540 + (ey - 100) * 3)
                for ex, ey in enemies
            ]
            self._combat.update(screen_enemies)
            time.sleep(0.1)

        self._combat.reset()
        logger.info("Seal area cleared")

    def boss_fight(self) -> None:
        """Fight Diablo after all seals are opened."""
        logger.info("Waiting for Diablo to spawn...")
        time.sleep(5.0)

        logger.info("Engaging Diablo")
        self._combat.engage_boss(960, 400)

        max_duration = 120.0
        start = time.time()

        while (time.time() - start) < max_duration:
            if self.check_chicken():
                return

            self._health.update()
            needs_chicken = self._health.manage_potions()
            if needs_chicken:
                return

            enemies = self._map.find_enemies()
            if not enemies:
                logger.info("Diablo killed!")
                break

            screen_enemies = [
                (960 + (ex - 130) * 3, 540 + (ey - 100) * 3)
                for ex, ey in enemies
            ]
            self._combat.update(screen_enemies)
            time.sleep(0.1)

        self._combat.reset()

    def loot(self) -> None:
        """Loot Diablo's drops."""
        logger.info("Looting Diablo drops")
        time.sleep(1.0)
        self._loot.scan_and_pickup()
        self._loot.quick_pickup()

    def return_to_town(self) -> None:
        """Return to town after Chaos run."""
        logger.info("Returning to town after Chaos run")
