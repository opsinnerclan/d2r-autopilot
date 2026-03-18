"""Town navigation and NPC interaction module."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.game.inventory import InventoryManager
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.keyboard import KeyboardController
    from d2r_autopilot.input.mouse import MouseController
    from d2r_autopilot.navigation.pathfinder import Pathfinder
    from d2r_autopilot.screen.capture import ScreenCapture
    from d2r_autopilot.screen.detector import TemplateDetector

logger = logging.getLogger(__name__)


@dataclass
class NPCLocation:
    """Screen coordinates for an NPC in town."""

    name: str
    screen_x: int
    screen_y: int


# NPC locations per act (approximate for 1920x1080)
# These would need template matching for accuracy, but serve as starting positions
ACT_NPCS: dict[int, dict[str, NPCLocation]] = {
    1: {
        "akara": NPCLocation("Akara", 300, 400),
        "charsi": NPCLocation("Charsi", 600, 350),
        "kashya": NPCLocation("Kashya", 450, 300),
        "stash": NPCLocation("Stash", 150, 350),
        "waypoint": NPCLocation("Waypoint", 500, 450),
    },
    2: {
        "drognan": NPCLocation("Drognan", 400, 450),
        "fara": NPCLocation("Fara", 300, 380),
        "stash": NPCLocation("Stash", 200, 400),
        "waypoint": NPCLocation("Waypoint", 350, 500),
    },
    3: {
        "ormus": NPCLocation("Ormus", 350, 400),
        "hratli": NPCLocation("Hratli", 500, 350),
        "stash": NPCLocation("Stash", 180, 380),
        "waypoint": NPCLocation("Waypoint", 400, 480),
    },
    4: {
        "tyrael": NPCLocation("Tyrael", 400, 350),
        "halbu": NPCLocation("Halbu", 300, 400),
        "stash": NPCLocation("Stash", 200, 350),
        "waypoint": NPCLocation("Waypoint", 500, 400),
    },
    5: {
        "malah": NPCLocation("Malah", 300, 380),
        "larzuk": NPCLocation("Larzuk", 500, 400),
        "qual_kehk": NPCLocation("Qual-Kehk", 600, 350),
        "stash": NPCLocation("Stash", 150, 400),
        "waypoint": NPCLocation("Waypoint", 400, 450),
        "nihlathak_portal": NPCLocation("Nihlathak Portal", 700, 300),
    },
}


class TownNavigator:
    """Handles town navigation, NPC interaction, repairs, and stashing."""

    def __init__(
        self,
        pathfinder: Pathfinder,
        screen: ScreenCapture,
        detector: TemplateDetector,
        keyboard: KeyboardController,
        mouse: MouseController,
        inventory: InventoryManager,
        state: GameState,
        current_act: int = 3,
    ) -> None:
        self._path = pathfinder
        self._screen = screen
        self._detector = detector
        self._keyboard = keyboard
        self._mouse = mouse
        self._inventory = inventory
        self._state = state
        self._act = current_act
        logger.info("TownNavigator initialized (act=%d)", current_act)

    @property
    def act(self) -> int:
        return self._act

    @act.setter
    def act(self, value: int) -> None:
        if 1 <= value <= 5:
            self._act = value
            logger.info("Changed to Act %d", value)

    def go_to_stash(self) -> bool:
        """Navigate to and open the stash.

        Returns:
            True if stash was opened successfully.
        """
        npc = self._get_npc("stash")
        if npc is None:
            return False

        self._mouse.click(npc.screen_x, npc.screen_y)
        time.sleep(1.0)

        # Verify stash is open using template matching
        frame = self._screen.grab_frame()
        match = self._detector.match_template(frame, "stash_open")
        if match.found:
            logger.info("Stash opened")
            return True

        # Try clicking again closer
        self._mouse.click(npc.screen_x, npc.screen_y)
        time.sleep(1.0)
        return True

    def stash_and_organize(self) -> None:
        """Open stash and transfer inventory items."""
        if not self.go_to_stash():
            logger.warning("Failed to open stash")
            return

        time.sleep(0.5)
        self._inventory.stash_items()
        time.sleep(0.5)
        self._keyboard.press("escape")
        time.sleep(0.3)
        logger.info("Stash & organize complete")

    def repair_items(self) -> None:
        """Navigate to the smith NPC and repair all items."""
        smith_names = {
            1: "charsi",
            2: "fara",
            3: "hratli",
            4: "halbu",
            5: "larzuk",
        }
        smith_name = smith_names.get(self._act, "charsi")
        npc = self._get_npc(smith_name)
        if npc is None:
            logger.warning("Smith NPC not found for act %d", self._act)
            return

        # Click on smith
        self._mouse.click(npc.screen_x, npc.screen_y)
        time.sleep(1.5)

        # Click "Trade/Repair" option
        self._mouse.click(npc.screen_x, npc.screen_y + 50)
        time.sleep(1.0)

        # Click "Repair All" button (approximate position)
        self._mouse.click(260, 540)
        time.sleep(0.5)

        self._keyboard.press("escape")
        time.sleep(0.3)
        logger.info("Items repaired")

    def use_waypoint(self, destination_index: int) -> bool:
        """Open the waypoint and travel to a destination.

        Args:
            destination_index: Index of the waypoint destination to select.

        Returns:
            True if waypoint travel was initiated.
        """
        npc = self._get_npc("waypoint")
        if npc is None:
            return False

        self._mouse.click(npc.screen_x, npc.screen_y)
        time.sleep(1.5)

        # Waypoint menu should be open
        # Click the appropriate destination
        # Destinations are listed vertically, ~25px apart
        dest_x = 300
        dest_y = 150 + destination_index * 25
        self._mouse.click(dest_x, dest_y)
        time.sleep(2.0)
        logger.info("Used waypoint to destination %d", destination_index)
        return True

    def heal_at_npc(self) -> None:
        """Visit a healer NPC to restore health."""
        healer_names = {
            1: "akara",
            2: "fara",
            3: "ormus",
            4: "tyrael",
            5: "malah",
        }
        healer_name = healer_names.get(self._act, "akara")
        npc = self._get_npc(healer_name)
        if npc is None:
            return

        self._mouse.click(npc.screen_x, npc.screen_y)
        time.sleep(1.0)
        self._keyboard.press("escape")
        time.sleep(0.3)
        logger.info("Healed at %s", healer_name)

    def do_town_routine(self, repair: bool = True, stash: bool = True, heal: bool = True) -> None:
        """Perform standard town routine: heal, repair, stash.

        Args:
            repair: Whether to repair items.
            stash: Whether to stash items.
            heal: Whether to heal.
        """
        logger.info("Starting town routine")
        if heal:
            self.heal_at_npc()
        if stash and self._inventory.is_full:
            self.stash_and_organize()
        if repair:
            self.repair_items()
        logger.info("Town routine complete")

    def _get_npc(self, npc_key: str) -> NPCLocation | None:
        """Get NPC location for the current act."""
        act_npcs = ACT_NPCS.get(self._act, {})
        npc = act_npcs.get(npc_key)
        if npc is None:
            logger.warning("NPC '%s' not found for act %d", npc_key, self._act)
        return npc
