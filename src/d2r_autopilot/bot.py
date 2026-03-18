"""Main bot controller - orchestrates all modules."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from d2r_autopilot.combat.engine import CombatEngine
from d2r_autopilot.config import BotConfig
from d2r_autopilot.game.health import HealthMonitor
from d2r_autopilot.game.inventory import InventoryManager
from d2r_autopilot.game.map_reader import MapReader
from d2r_autopilot.game.skills import SkillManager
from d2r_autopilot.game.state import GameScreen, GameState
from d2r_autopilot.input.keyboard import KeyboardController
from d2r_autopilot.input.mouse import MouseController
from d2r_autopilot.loot.filter import LootFilter
from d2r_autopilot.loot.picker import LootPicker
from d2r_autopilot.navigation.pathfinder import Pathfinder
from d2r_autopilot.navigation.town import TownNavigator
from d2r_autopilot.routines.baal import BaalRoutine
from d2r_autopilot.routines.base import BaseRoutine
from d2r_autopilot.routines.chaos import ChaosRoutine
from d2r_autopilot.routines.mephisto import MephistoRoutine
from d2r_autopilot.screen.capture import ScreenCapture
from d2r_autopilot.screen.detector import TemplateDetector
from d2r_autopilot.screen.ocr import GameOCR

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Bot:
    """Main bot controller that ties all modules together.

    Manages the game loop: creating games, running routines,
    and handling transitions between runs.
    """

    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._running = False
        self._paused = False

        # Initialize all subsystems
        self._state = GameState()
        self._screen = ScreenCapture(config.screen)
        self._detector = TemplateDetector(config.screen.template_match_threshold)
        self._ocr = GameOCR()
        self._keyboard = KeyboardController(config.input)
        self._mouse = MouseController(config.input)
        self._skill_manager = SkillManager(config.character, self._keyboard, self._mouse)
        self._health_monitor = HealthMonitor(
            config.screen.health_bar,
            self._screen,
            self._keyboard,
            self._state,
            config.character.potion_keys,
        )
        self._inventory = InventoryManager(
            config.screen, self._screen, self._detector,
            self._keyboard, self._mouse, self._state,
        )
        self._map_reader = MapReader(config.navigation, self._screen, self._state)
        self._pathfinder = Pathfinder(
            config.navigation, self._map_reader, self._skill_manager,
            self._mouse, self._state,
        )
        self._loot_filter = LootFilter(config.loot)
        self._loot_picker = LootPicker(
            config.loot, self._loot_filter, self._screen, self._ocr,
            self._keyboard, self._mouse, self._inventory, self._state,
        )
        self._town = TownNavigator(
            self._pathfinder, self._screen, self._detector,
            self._keyboard, self._mouse, self._inventory, self._state,
        )

        # Select the farming routine
        self._routine = self._create_routine(config.routine.name)

        logger.info(
            "Bot initialized (class=%s, routine=%s)",
            config.character.character_class,
            config.routine.name,
        )

    def _create_routine(self, routine_name: str) -> BaseRoutine:
        """Create a farming routine by name.

        Args:
            routine_name: Name of the routine ('mephisto', 'chaos', 'baal').

        Returns:
            The farming routine instance.
        """
        routine_args = (
            self._config.routine,
            self._state,
            CombatEngine(
                self._config.character,
                self._skill_manager,
                self._health_monitor,
                self._mouse,
                self._state,
            ),
            self._pathfinder,
            self._town,
            self._map_reader,
            self._health_monitor,
            self._loot_picker,
        )

        routines: dict[str, type[BaseRoutine]] = {
            "mephisto": MephistoRoutine,
            "chaos": ChaosRoutine,
            "baal": BaalRoutine,
        }

        routine_class = routines.get(routine_name.lower())
        if routine_class is None:
            logger.warning("Unknown routine '%s', defaulting to mephisto", routine_name)
            routine_class = MephistoRoutine

        return routine_class(*routine_args)

    def start(self) -> None:
        """Start the bot's main loop."""
        self._running = True
        logger.info("Bot starting...")

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
        except Exception:
            logger.exception("Bot crashed")
        finally:
            self.stop()

    def _main_loop(self) -> None:
        """Main bot loop: create games, run routines, repeat."""
        max_runs = self._config.max_runs
        run_number = 0

        while self._running:
            if self._paused:
                time.sleep(1.0)
                continue

            run_number += 1
            if max_runs > 0 and run_number > max_runs:
                logger.info("Max runs reached (%d), stopping", max_runs)
                break

            logger.info("=== Starting run %d ===", run_number)

            # Wait for the game to be ready
            self._wait_for_game_ready()

            # Create a new game
            self._create_new_game()

            # Wait for loading
            self._wait_for_loading()

            # Execute the farming routine
            success = self._routine.run()

            if success:
                logger.info("Run %d completed successfully", run_number)
            else:
                logger.warning("Run %d failed", run_number)

            # Exit the game and wait
            self._exit_game()
            self._wait_between_games()

            # Print stats
            stats = self._state.get_stats()
            logger.info(
                "Stats: games=%d, deaths=%d, items=%d",
                stats["games"], stats["deaths"], stats["items_picked"],
            )

    def _wait_for_game_ready(self) -> None:
        """Wait until the game is at the character select or main menu."""
        logger.debug("Waiting for game ready state...")
        max_wait = 30.0
        start = time.time()

        while (time.time() - start) < max_wait:
            frame = self._screen.grab_frame()

            # Check for character select screen
            match = self._detector.match_template(frame, "char_select")
            if match.found:
                self._state.screen = GameScreen.CHARACTER_SELECT
                return

            # Check for main menu
            match = self._detector.match_template(frame, "main_menu")
            if match.found:
                self._state.screen = GameScreen.MAIN_MENU
                return

            # Check if already in game
            match = self._detector.match_template(frame, "in_game_hud")
            if match.found:
                self._state.screen = GameScreen.IN_GAME
                return

            time.sleep(1.0)

        logger.warning("Timeout waiting for game ready")

    def _create_new_game(self) -> None:
        """Create a new game from the lobby/menu."""
        logger.info("Creating new game...")
        self._state.start_new_game()

        # Press "Create Game" or equivalent
        # This is highly dependent on the game state
        # For online: lobby -> create game
        # For offline: character select -> play

        # Simulate clicking "Play" on character select
        self._mouse.click(400, 500)
        time.sleep(1.0)
        self._mouse.click(700, 450)  # Create game button
        time.sleep(1.0)
        self._mouse.click(700, 550)  # Confirm / set difficulty
        time.sleep(2.0)

    def _wait_for_loading(self) -> None:
        """Wait for the loading screen to finish."""
        logger.debug("Waiting for loading...")
        self._state.screen = GameScreen.LOADING

        max_wait = 30.0
        start = time.time()

        while (time.time() - start) < max_wait:
            frame = self._screen.grab_frame()

            # Check if we're in game now
            match = self._detector.match_template(frame, "in_game_hud")
            if match.found:
                self._state.screen = GameScreen.IN_GAME
                logger.info("Game loaded")
                time.sleep(1.0)  # Brief settle time
                return

            time.sleep(0.5)

        logger.warning("Loading timeout")

    def _exit_game(self) -> None:
        """Exit the current game."""
        logger.info("Exiting game...")
        # Save and exit
        self._keyboard.press("escape")
        time.sleep(0.5)
        # Click "Save and Exit"
        self._mouse.click(400, 340)
        time.sleep(2.0)

    def _wait_between_games(self) -> None:
        """Wait the minimum time between games to avoid rate limiting."""
        min_time = self._config.routine.min_game_time
        elapsed = self._state.game_elapsed
        if elapsed < min_time:
            wait_time = min_time - elapsed
            logger.info("Waiting %.1fs between games", wait_time)
            time.sleep(wait_time)

    def stop(self) -> None:
        """Stop the bot."""
        self._running = False
        self._keyboard.release_all()
        self._screen.close()
        logger.info("Bot stopped. Final stats: %s", self._state.get_stats())

    def pause(self) -> None:
        """Pause the bot."""
        self._paused = True
        self._keyboard.release_all()
        logger.info("Bot paused")

    def resume(self) -> None:
        """Resume the bot."""
        self._paused = False
        logger.info("Bot resumed")
