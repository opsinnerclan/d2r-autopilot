"""Inventory management module."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.config import ScreenConfig
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.keyboard import KeyboardController
    from d2r_autopilot.input.mouse import MouseController
    from d2r_autopilot.screen.capture import ScreenCapture
    from d2r_autopilot.screen.detector import TemplateDetector

logger = logging.getLogger(__name__)

# Inventory grid constants (1920x1080 resolution)
INVENTORY_TOP_LEFT = (1103, 418)
INVENTORY_SLOT_SIZE = 29
INVENTORY_COLS = 10
INVENTORY_ROWS = 4

STASH_TOP_LEFT = (153, 418)
STASH_COLS = 10
STASH_ROWS = 10


class InventoryManager:
    """Manages the player's inventory: checking space, identifying items, stashing."""

    def __init__(
        self,
        config: ScreenConfig,
        screen: ScreenCapture,
        detector: TemplateDetector,
        keyboard: KeyboardController,
        mouse: MouseController,
        state: GameState,
    ) -> None:
        self._config = config
        self._screen = screen
        self._detector = detector
        self._keyboard = keyboard
        self._mouse = mouse
        self._state = state
        self._inventory_slots: list[list[bool]] = [
            [False] * INVENTORY_COLS for _ in range(INVENTORY_ROWS)
        ]
        logger.info("InventoryManager initialized")

    def open_inventory(self) -> None:
        """Open the inventory screen."""
        self._keyboard.press("i")
        time.sleep(0.5)
        logger.debug("Inventory opened")

    def close_inventory(self) -> None:
        """Close the inventory screen."""
        self._keyboard.press("escape")
        time.sleep(0.3)
        logger.debug("Inventory closed")

    def has_space(self, width: int = 1, height: int = 1) -> bool:
        """Check if inventory has space for an item of given size.

        Args:
            width: Item width in grid slots.
            height: Item height in grid slots.

        Returns:
            True if there's space for the item.
        """
        for row in range(INVENTORY_ROWS - height + 1):
            for col in range(INVENTORY_COLS - width + 1):
                if self._check_slot_range(row, col, width, height):
                    return True
        return False

    def _check_slot_range(self, row: int, col: int, width: int, height: int) -> bool:
        """Check if a range of slots is empty."""
        for r in range(row, row + height):
            for c in range(col, col + width):
                if self._inventory_slots[r][c]:
                    return False
        return True

    def update_slots(self) -> None:
        """Scan the inventory to update slot occupancy.

        Captures the inventory region and checks each slot for items.
        """
        self.open_inventory()
        time.sleep(0.3)

        frame = self._screen.grab_frame()
        for row in range(INVENTORY_ROWS):
            for col in range(INVENTORY_COLS):
                slot_x = INVENTORY_TOP_LEFT[0] + col * INVENTORY_SLOT_SIZE
                slot_y = INVENTORY_TOP_LEFT[1] + row * INVENTORY_SLOT_SIZE
                # Check if the slot has an item by looking at pixel intensity
                slot_region = frame[
                    slot_y : slot_y + INVENTORY_SLOT_SIZE,
                    slot_x : slot_x + INVENTORY_SLOT_SIZE,
                ]
                mean_intensity = float(slot_region.mean())
                self._inventory_slots[row][col] = mean_intensity > 40

        self.close_inventory()
        occupied = sum(
            1 for row in self._inventory_slots for slot in row if slot
        )
        total = INVENTORY_ROWS * INVENTORY_COLS
        logger.info("Inventory scan: %d/%d slots occupied", occupied, total)

    @property
    def is_full(self) -> bool:
        """Whether the inventory is full."""
        return not self.has_space(1, 1)

    @property
    def free_slots(self) -> int:
        """Number of free single-slot spaces."""
        return sum(
            1 for row in self._inventory_slots for slot in row if not slot
        )

    def stash_items(self) -> None:
        """Transfer items from inventory to stash.

        Assumes the stash is already open. Ctrl+clicks items to transfer.
        """
        logger.info("Stashing items...")
        for row in range(INVENTORY_ROWS):
            for col in range(INVENTORY_COLS):
                if self._inventory_slots[row][col]:
                    base_x = INVENTORY_TOP_LEFT[0] + col * INVENTORY_SLOT_SIZE
                    base_y = INVENTORY_TOP_LEFT[1] + row * INVENTORY_SLOT_SIZE
                    slot_x = base_x + INVENTORY_SLOT_SIZE // 2
                    slot_y = base_y + INVENTORY_SLOT_SIZE // 2
                    # Ctrl+click to transfer to stash
                    self._keyboard.hold("ctrl")
                    self._mouse.click(slot_x, slot_y)
                    self._keyboard.release("ctrl")
                    time.sleep(0.2)

        logger.info("Stashing complete")

    def drop_item(self, row: int, col: int) -> None:
        """Drop an item at the given inventory slot.

        Args:
            row: Inventory row.
            col: Inventory column.
        """
        slot_x = INVENTORY_TOP_LEFT[0] + col * INVENTORY_SLOT_SIZE + INVENTORY_SLOT_SIZE // 2
        slot_y = INVENTORY_TOP_LEFT[1] + row * INVENTORY_SLOT_SIZE + INVENTORY_SLOT_SIZE // 2
        self._mouse.click(slot_x, slot_y)
        time.sleep(0.1)
        # Click outside inventory to drop
        self._mouse.click(400, 400)
        time.sleep(0.2)
        self._inventory_slots[row][col] = False
        logger.info("Dropped item at (%d, %d)", row, col)
