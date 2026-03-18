"""Baal farming routine - Act 5 Hell."""

from __future__ import annotations

import logging
import time

from d2r_autopilot.routines.base import BaseRoutine

logger = logging.getLogger(__name__)

WORLDSTONE_KEEP_2_WP = 5  # Act 5 waypoint index


class BaalRoutine(BaseRoutine):
    """Farms Baal in the Worldstone Chamber.

    Strategy:
    1. Waypoint to Worldstone Keep Level 2
    2. Find stairs to Level 3
    3. Navigate to Throne of Destruction
    4. Clear Baal's 5 minion waves
    5. Enter Worldstone Chamber and kill Baal
    6. Loot and return to town
    """

    @property
    def name(self) -> str:
        return "BaalRun"

    def town_prep(self) -> None:
        """Prepare in Harrogath."""
        logger.info("Town prep for Baal run")
        self._town.act = 5
        should_repair = self._run_count % (self._config.repair_interval or 10) == 0
        should_stash = self._run_count % (self._config.stash_interval or 5) == 0
        self._town.do_town_routine(
            repair=should_repair,
            stash=should_stash,
            heal=True,
        )

    def navigate(self) -> bool:
        """Navigate from Harrogath to the Throne of Destruction.

        Returns:
            True if successfully reached the Throne.
        """
        logger.info("Navigating to Throne of Destruction")

        # Waypoint to Worldstone Keep Level 2
        if not self._town.use_waypoint(WORLDSTONE_KEEP_2_WP):
            logger.error("Failed to use WSK2 waypoint")
            return False

        time.sleep(2.0)

        # Navigate through WSK2 -> WSK3 -> Throne of Destruction
        levels = ["WSK2->WSK3", "WSK3->Throne"]
        for level_transition in levels:
            logger.info("Navigating: %s", level_transition)
            if not self._find_and_take_exit():
                logger.error("Failed to navigate: %s", level_transition)
                return False
            time.sleep(2.0)

        logger.info("Reached Throne of Destruction")
        return True

    def _find_and_take_exit(self) -> bool:
        """Find and take the exit to the next level.

        Returns:
            True if exit was found and taken.
        """
        max_teleports = 60
        for i in range(max_teleports):
            if self.check_timeout() or self.check_chicken():
                return False

            exit_pos = self._map.find_exit()
            if exit_pos is not None:
                while not self._path.is_near(exit_pos, threshold=20):
                    if self.check_timeout():
                        return False
                    self._path.move_toward_minimap(*exit_pos)
                    time.sleep(0.3)

                # Click to enter
                screen_x = 960 + (exit_pos[0] - 130) * 3
                screen_y = 540 + (exit_pos[1] - 100) * 3
                self._path.move_to_screen(screen_x, screen_y)
                time.sleep(2.0)
                return True

            self._path.explore()

            if i % 15 == 0:
                logger.debug("Searching for exit... (%d/%d)", i, max_teleports)

        return False

    def clear(self) -> None:
        """Clear Baal's 5 minion waves in the Throne of Destruction."""
        logger.info("Clearing Baal's minion waves")

        for wave in range(1, 6):
            logger.info("Waiting for wave %d/5...", wave)
            self._wait_for_wave()
            self._clear_wave(wave)
            time.sleep(2.0)

        logger.info("All 5 waves cleared")

    def _wait_for_wave(self) -> None:
        """Wait for the next wave of minions to spawn."""
        max_wait = 30.0
        start = time.time()

        while (time.time() - start) < max_wait:
            enemies = self._map.find_enemies()
            if enemies:
                return
            time.sleep(0.5)

        logger.warning("Wave wait timeout")

    def _clear_wave(self, wave_number: int) -> None:
        """Clear a single minion wave.

        Args:
            wave_number: Which wave (1-5).
        """
        logger.info("Clearing wave %d", wave_number)
        max_clear_time = 45.0
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
                logger.info("Wave %d cleared", wave_number)
                break

            screen_enemies = [
                (960 + (ex - 130) * 3, 540 + (ey - 100) * 3)
                for ex, ey in enemies
            ]
            self._combat.update(screen_enemies)
            time.sleep(0.1)

        self._combat.reset()

    def boss_fight(self) -> None:
        """Enter the Worldstone Chamber and fight Baal."""
        logger.info("Entering Worldstone Chamber to fight Baal")
        # Click on the portal that Baal opens
        time.sleep(3.0)

        # Find and click the portal
        exit_pos = self._map.find_exit()
        if exit_pos is not None:
            self._path.move_toward_minimap(*exit_pos)
            time.sleep(3.0)

        # Fight Baal
        logger.info("Engaging Baal")
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
                logger.info("Baal killed!")
                break

            screen_enemies = [
                (960 + (ex - 130) * 3, 540 + (ey - 100) * 3)
                for ex, ey in enemies
            ]
            self._combat.update(screen_enemies)
            time.sleep(0.1)

        self._combat.reset()

    def loot(self) -> None:
        """Loot Baal's drops."""
        logger.info("Looting Baal drops")
        time.sleep(1.0)
        self._loot.scan_and_pickup()
        self._loot.quick_pickup()

    def return_to_town(self) -> None:
        """Return to town after Baal run."""
        logger.info("Returning to town after Baal run")
