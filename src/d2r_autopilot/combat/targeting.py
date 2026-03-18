"""Target selection and priority management for combat."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class TargetPriority(IntEnum):
    """Priority levels for targeting."""

    IGNORE = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    BOSS = 4
    CRITICAL = 5


@dataclass
class Target:
    """Represents a targetable entity on screen."""

    screen_x: int
    screen_y: int
    minimap_x: int = 0
    minimap_y: int = 0
    priority: TargetPriority = TargetPriority.NORMAL
    name: str = ""
    is_unique: bool = False
    estimated_hp_pct: float = 1.0


@dataclass
class TargetList:
    """Ordered list of targets sorted by priority and distance."""

    targets: list[Target] = field(default_factory=list)

    @property
    def has_targets(self) -> bool:
        return len(self.targets) > 0

    @property
    def primary(self) -> Target | None:
        """Highest priority target."""
        if not self.targets:
            return None
        return self.targets[0]

    @property
    def count(self) -> int:
        return len(self.targets)

    def add(self, target: Target) -> None:
        self.targets.append(target)
        self._sort()

    def remove(self, target: Target) -> None:
        if target in self.targets:
            self.targets.remove(target)

    def clear(self) -> None:
        self.targets.clear()

    def _sort(self) -> None:
        """Sort by priority (desc), then distance from screen center."""
        center_x, center_y = 960, 540
        self.targets.sort(
            key=lambda t: (
                -t.priority,
                math.sqrt((t.screen_x - center_x) ** 2 + (t.screen_y - center_y) ** 2),
            )
        )


class TargetSelector:
    """Selects combat targets based on screen analysis."""

    def __init__(self) -> None:
        self._known_boss_names: set[str] = {
            "Andariel", "Duriel", "Mephisto", "Diablo", "Baal",
            "The Summoner", "Nihlathak", "Pindleskin", "Shenk",
            "Eldritch", "Thresh Socket", "Snapchip Shatter",
        }
        self._ignore_list: set[str] = set()
        logger.info("TargetSelector initialized")

    def evaluate_targets(
        self,
        enemy_positions: list[tuple[int, int]],
        screen_center: tuple[int, int] = (960, 540),
    ) -> TargetList:
        """Convert detected enemy positions into prioritized targets.

        Args:
            enemy_positions: List of (x, y) screen positions of enemies.
            screen_center: Center of the game screen.

        Returns:
            Sorted TargetList.
        """
        target_list = TargetList()

        for pos_x, pos_y in enemy_positions:
            distance = math.sqrt(
                (pos_x - screen_center[0]) ** 2 + (pos_y - screen_center[1]) ** 2
            )

            # Closer enemies get higher priority
            if distance < 200:
                priority = TargetPriority.HIGH
            elif distance < 400:
                priority = TargetPriority.NORMAL
            else:
                priority = TargetPriority.LOW

            target = Target(
                screen_x=pos_x,
                screen_y=pos_y,
                priority=priority,
            )
            target_list.add(target)

        if target_list.has_targets:
            logger.debug("Found %d targets", target_list.count)

        return target_list

    def find_boss(
        self,
        targets: TargetList,
        boss_name: str,
    ) -> Target | None:
        """Find a specific boss in the target list.

        Args:
            targets: Current target list.
            boss_name: Name of the boss to find.

        Returns:
            Boss Target if found.
        """
        for target in targets.targets:
            if target.name == boss_name:
                target.priority = TargetPriority.BOSS
                return target
        return None

    def closest_target(
        self,
        targets: TargetList,
        from_x: int,
        from_y: int,
    ) -> Target | None:
        """Find the closest target to a given position.

        Args:
            targets: Available targets.
            from_x: Reference X position.
            from_y: Reference Y position.

        Returns:
            Closest Target, or None.
        """
        if not targets.has_targets:
            return None

        closest: Target | None = None
        min_dist = float("inf")

        for target in targets.targets:
            dist = math.sqrt(
                (target.screen_x - from_x) ** 2 + (target.screen_y - from_y) ** 2
            )
            if dist < min_dist:
                min_dist = dist
                closest = target

        return closest
