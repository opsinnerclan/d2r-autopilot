"""Loot filtering module - determines which items to pick up."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.config import LootConfig, LootRule

logger = logging.getLogger(__name__)


class ItemQuality(Enum):
    """D2R item quality tiers."""

    NORMAL = auto()      # White
    SUPERIOR = auto()    # White with "Superior"
    MAGIC = auto()       # Blue
    RARE = auto()        # Yellow
    SET = auto()         # Green
    UNIQUE = auto()      # Gold/Brown
    CRAFTED = auto()     # Orange
    RUNEWORD = auto()    # Gold


# Map text colors to item quality (approximate HSV ranges for item name colors)
QUALITY_COLORS: dict[str, ItemQuality] = {
    "white": ItemQuality.NORMAL,
    "blue": ItemQuality.MAGIC,
    "yellow": ItemQuality.RARE,
    "green": ItemQuality.SET,
    "gold": ItemQuality.UNIQUE,
    "orange": ItemQuality.CRAFTED,
}


@dataclass
class DetectedItem:
    """An item detected on the ground."""

    name: str
    screen_x: int
    screen_y: int
    color: str = "white"
    quality: ItemQuality = ItemQuality.NORMAL
    should_pickup: bool = False
    priority: int = 0


class LootFilter:
    """Filters ground items based on configurable rules."""

    def __init__(self, config: LootConfig) -> None:
        self._config = config
        self._compiled_rules: list[tuple[re.Pattern[str], LootRule]] = []
        self._compile_rules()
        logger.info("LootFilter initialized (%d rules)", len(self._compiled_rules))

    def _compile_rules(self) -> None:
        """Pre-compile regex patterns for all loot rules."""
        for rule in self._config.rules:
            try:
                pattern = re.compile(rule.name_pattern, re.IGNORECASE)
                self._compiled_rules.append((pattern, rule))
            except re.error:
                logger.error("Invalid loot rule pattern: %s", rule.name_pattern)

    def evaluate(self, item: DetectedItem) -> DetectedItem:
        """Evaluate an item against all loot rules.

        Args:
            item: The detected item to evaluate.

        Returns:
            The item with should_pickup and priority set.
        """
        if not self._config.enabled:
            return item

        for pattern, rule in self._compiled_rules:
            if not pattern.search(item.name):
                continue

            # Check color filter
            if rule.color != "any" and item.color != rule.color:
                continue

            # Check quality filter
            if rule.quality != "any":
                expected_quality = QUALITY_COLORS.get(rule.quality)
                if expected_quality is not None and item.quality != expected_quality:
                    continue

            item.should_pickup = rule.pick_up
            item.priority = rule.priority
            logger.debug(
                "Item '%s' matched rule '%s' (pickup=%s, priority=%d)",
                item.name, rule.name_pattern, rule.pick_up, rule.priority,
            )
            return item

        # No rule matched - don't pick up by default
        item.should_pickup = False
        item.priority = 0
        return item

    def filter_items(self, items: list[DetectedItem]) -> list[DetectedItem]:
        """Filter and sort a list of detected items.

        Args:
            items: List of items to filter.

        Returns:
            Items that should be picked up, sorted by priority (highest first).
        """
        evaluated = [self.evaluate(item) for item in items]
        pickups = [item for item in evaluated if item.should_pickup]
        pickups.sort(key=lambda i: i.priority, reverse=True)
        return pickups

    def add_rule(self, rule: LootRule) -> None:
        """Add a new loot rule at runtime.

        Args:
            rule: The loot rule to add.
        """
        try:
            pattern = re.compile(rule.name_pattern, re.IGNORECASE)
            self._compiled_rules.append((pattern, rule))
            self._config.rules.append(rule)
            logger.info("Added loot rule: %s", rule.name_pattern)
        except re.error:
            logger.error("Invalid rule pattern: %s", rule.name_pattern)

    def is_valuable(self, item: DetectedItem) -> bool:
        """Quick check if an item is potentially valuable.

        Args:
            item: Item to check.

        Returns:
            True if the item matches any pickup rule.
        """
        evaluated = self.evaluate(item)
        return evaluated.should_pickup
