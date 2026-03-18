"""Mephisto farming routine - Act 3 Hell."""

from __future__ import annotations

import logging
import time

from d2r_autopilot.routines.base import BaseRoutine

logger = logging.getLogger(__name__)

# Waypoint index for Durance of Hate Level 2
DURANCE_LVL2_WP = 7  # Act 3 waypoint list index


class MephistoRoutine(BaseRoutine):
    """Farms Mephisto in Durance of Hate Level 3.

    Strategy:
    1. Take waypoint to Durance of Hate Level 2
    2. Teleport to find the stairs to Level 3
    3. Teleport across the moat to Mephisto
    4. Kill Mephisto using moat trick or direct combat
    5. Loot and return to town
    """

    @property
    def name(self) -> str:
        return "MephistoRun"

    def town_prep(self) -> None:
        """Prepare in Kurast Docks."""
        logger.info("Town prep: healing, repairing")
        should_repair = self._run_count % (self._config.repair_interval or 10) == 0
        should_stash = self._run_count % (self._config.stash_interval or 5) == 0
        self._town.do_town_routine(
            repair=should_repair,
            stash=should_stash,
            heal=True,
        )

    def navigate(self) -> bool:
        """Navigate from Kurast Docks to Durance of Hate Level 3.

        Uses waypoint to DH2, then teleports to find the exit to DH3.

        Returns:
            True if successfully reached DH3.
        """
        logger.info("Navigating to Durance of Hate Level 3")

        # Step 1: Use waypoint to Durance Level 2
        if not self._town.use_waypoint(DURANCE_LVL2_WP):
            logger.error("Failed to use Durance L2 waypoint")
            return False

        time.sleep(2.0)

        # Step 2: Teleport to find the exit to Level 3
        max_teleports = 50
        for i in range(max_teleports):
            if self.check_timeout() or self.check_chicken():
                return False

            # Look for the exit/stairs on minimap
            exit_pos = self._map.find_exit()
            if exit_pos is not None:
                logger.info("Found DH3 exit on minimap at %s", exit_pos)
                # Navigate to the exit
                while not self._path.is_near(exit_pos, threshold=20):
                    if self.check_timeout() or self.check_chicken():
                        return False
                    self._path.move_toward_minimap(*exit_pos)
                    time.sleep(0.3)

                # Click the exit
                # Convert minimap position to approximate screen position
                screen_x = 960 + (exit_pos[0] - 130) * 3
                screen_y = 540 + (exit_pos[1] - 100) * 3
                # Click to enter
                self._path.move_to_screen(screen_x, screen_y)
                time.sleep(2.0)
                logger.info("Entered Durance of Hate Level 3")
                return True

            # Explore by teleporting in a search pattern
            self._path.explore()

            if i % 10 == 0:
                logger.debug("Searching for DH3 exit... (teleport %d/%d)", i, max_teleports)

        logger.error("Failed to find DH3 exit after %d teleports", max_teleports)
        return False

    def clear(self) -> None:
        """Clear path to Mephisto (mostly skip trash mobs)."""
        logger.info("Skipping trash, heading to Mephisto")
        # In a typical Mephisto run, we teleport past everything

    def boss_fight(self) -> None:
        """Fight Mephisto.

        Strategy depends on character class:
        - Sorceress: Moat trick (static field + blizzard from across moat)
        - Paladin: Direct combat with Blessed Hammer
        """
        logger.info("Engaging Mephisto")
        self._combat.engage_boss(960, 400)

        # Find enemies on screen and fight
        max_duration = 60.0
        start = time.time()

        while (time.time() - start) < max_duration:
            if self.check_chicken():
                return

            # Update health
            self._health.update()
            needs_chicken = self._health.manage_potions()
            if needs_chicken:
                logger.warning("Chickening during Mephisto fight")
                return

            # Detect enemies
            enemies = self._map.find_enemies()
            if not enemies:
                # Check if Mephisto is dead by looking for loot
                logger.info("No enemies detected, Mephisto likely dead")
                break

            # Convert minimap enemy positions to screen positions (approximate)
            screen_enemies = [
                (960 + (ex - 130) * 3, 540 + (ey - 100) * 3)
                for ex, ey in enemies
            ]

            still_fighting = self._combat.update(screen_enemies)
            if not still_fighting:
                break

            time.sleep(0.1)

        self._combat.reset()
        logger.info("Mephisto fight complete")

    def loot(self) -> None:
        """Pick up loot from Mephisto."""
        logger.info("Looting Mephisto drops")
        time.sleep(0.5)
        self._loot.scan_and_pickup()
        # Quick pickup for anything nearby
        self._loot.quick_pickup()

    def return_to_town(self) -> None:
        """Return to town via Town Portal."""
        logger.info("Casting Town Portal to return")
        # TP back handled by bot controller
