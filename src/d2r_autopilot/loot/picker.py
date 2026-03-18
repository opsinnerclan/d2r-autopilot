"""Loot pickup logic - detects and picks up items from the ground."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from d2r_autopilot.loot.filter import QUALITY_COLORS, DetectedItem, ItemQuality, LootFilter
from d2r_autopilot.screen.detector import ColorDetector

if TYPE_CHECKING:
    from d2r_autopilot.config import LootConfig
    from d2r_autopilot.game.inventory import InventoryManager
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.keyboard import KeyboardController
    from d2r_autopilot.input.mouse import MouseController
    from d2r_autopilot.screen.capture import ScreenCapture
    from d2r_autopilot.screen.ocr import GameOCR

logger = logging.getLogger(__name__)

# Item name label color ranges in HSV
ITEM_LABEL_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "white": ((0, 0, 200), (180, 30, 255)),
    "blue": ((100, 100, 150), (130, 255, 255)),
    "yellow": ((20, 150, 150), (35, 255, 255)),
    "green": ((35, 100, 150), (85, 255, 255)),
    "gold": ((15, 100, 150), (25, 255, 255)),
    "orange": ((5, 150, 150), (20, 255, 255)),
}


class LootPicker:
    """Detects items on the ground and picks them up based on filter rules."""

    def __init__(
        self,
        config: LootConfig,
        loot_filter: LootFilter,
        screen: ScreenCapture,
        ocr: GameOCR,
        keyboard: KeyboardController,
        mouse: MouseController,
        inventory: InventoryManager,
        state: GameState,
    ) -> None:
        self._config = config
        self._filter = loot_filter
        self._screen = screen
        self._ocr = ocr
        self._keyboard = keyboard
        self._mouse = mouse
        self._inventory = inventory
        self._state = state
        self._pickup_attempts: int = 0
        logger.info("LootPicker initialized")

    def scan_and_pickup(self) -> int:
        """Scan for items on the ground and pick up valuable ones.

        Returns:
            Number of items picked up.
        """
        if not self._config.enabled:
            return 0

        # Show item labels
        self._keyboard.hold(self._config.show_items_key)
        time.sleep(0.3)

        # Capture screen with labels visible
        frame = self._screen.grab_frame()

        # Detect item labels
        items = self._detect_items(frame)

        # Filter items
        to_pickup = self._filter.filter_items(items)

        picked = 0
        for item in to_pickup:
            if self._inventory.is_full:
                logger.warning("Inventory full, stopping pickup")
                break

            if self._pick_item(item):
                picked += 1
                self._state.items_picked += 1

        # Release alt key
        self._keyboard.release(self._config.show_items_key)

        if picked > 0:
            logger.info("Picked up %d items", picked)

        return picked

    def _detect_items(self, frame: np.ndarray) -> list[DetectedItem]:
        """Detect item labels on the ground.

        Looks for colored text rectangles that indicate item names.

        Args:
            frame: Full game screen capture.

        Returns:
            List of detected items.
        """
        items: list[DetectedItem] = []
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for color_name, (lower, upper) in ITEM_LABEL_COLORS.items():
            lower_np = np.array(lower, dtype=np.uint8)
            upper_np = np.array(upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_np, upper_np)

            # Find contours of text regions
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 200 or area > 10000:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                # Item labels are typically wider than tall
                if w < h:
                    continue

                # Read item name using OCR
                label_region = frame[y : y + h, x : x + w]
                item_name = self._ocr.read_item_name(label_region)

                if not item_name:
                    item_name = f"Unknown_{color_name}"

                quality = QUALITY_COLORS.get(color_name, ItemQuality.NORMAL)

                item = DetectedItem(
                    name=item_name,
                    screen_x=x + w // 2,
                    screen_y=y + h // 2,
                    color=color_name,
                    quality=quality,
                )
                items.append(item)

        logger.debug("Detected %d item labels on ground", len(items))
        return items

    def _pick_item(self, item: DetectedItem) -> bool:
        """Attempt to pick up an item by clicking on it.

        Args:
            item: The item to pick up.

        Returns:
            True if pickup was successful.
        """
        logger.info("Picking up: %s at (%d, %d)", item.name, item.screen_x, item.screen_y)

        # Move to item and click
        self._mouse.click(item.screen_x, item.screen_y)
        time.sleep(0.4)

        # Verify pickup by checking if label disappeared
        self._keyboard.hold(self._config.show_items_key)
        time.sleep(0.2)
        frame = self._screen.grab_frame()
        self._keyboard.release(self._config.show_items_key)

        # Simple check: see if there's still a colored label at that position
        region = frame[
            max(0, item.screen_y - 15) : item.screen_y + 15,
            max(0, item.screen_x - 50) : item.screen_x + 50,
        ]

        color_info = ITEM_LABEL_COLORS.get(item.color)
        if color_info is not None:
            match = ColorDetector.detect_color(region, color_info[0], color_info[1])
            if match.found and match.pixel_count > 50:
                # Item still there, try again
                self._mouse.click(item.screen_x, item.screen_y)
                time.sleep(0.3)

        self._pickup_attempts += 1
        return True

    def quick_pickup(self) -> None:
        """Quick pickup of nearby items without full scan.

        Rapidly clicks near the character to grab items in immediate vicinity.
        """
        center_x, center_y = 960, 540
        offsets = [
            (0, 0), (-30, -30), (30, -30), (-30, 30), (30, 30),
            (0, -50), (0, 50), (-50, 0), (50, 0),
        ]

        self._keyboard.hold(self._config.show_items_key)
        time.sleep(0.2)

        for dx, dy in offsets:
            self._mouse.click(center_x + dx, center_y + dy)
            time.sleep(0.1)

        self._keyboard.release(self._config.show_items_key)
