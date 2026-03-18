"""Combat engine - handles fighting, kiting, and skill rotation."""

from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

from d2r_autopilot.combat.targeting import TargetList, TargetPriority, TargetSelector

if TYPE_CHECKING:
    from d2r_autopilot.config import CharacterConfig
    from d2r_autopilot.game.health import HealthMonitor
    from d2r_autopilot.game.skills import SkillManager
    from d2r_autopilot.game.state import GameState
    from d2r_autopilot.input.mouse import MouseController

logger = logging.getLogger(__name__)


class CombatState(Enum):
    """States of the combat engine."""

    IDLE = auto()
    ENGAGING = auto()
    ATTACKING = auto()
    KITING = auto()
    RETREATING = auto()
    LOOTING = auto()


class CombatEngine:
    """Manages combat encounters: target selection, attack patterns, and kiting."""

    def __init__(
        self,
        character_config: CharacterConfig,
        skill_manager: SkillManager,
        health_monitor: HealthMonitor,
        mouse: MouseController,
        state: GameState,
    ) -> None:
        self._char_config = character_config
        self._skills = skill_manager
        self._health = health_monitor
        self._mouse = mouse
        self._state = state
        self._target_selector = TargetSelector()
        self._combat_state = CombatState.IDLE
        self._attack_start_time: float = 0.0
        self._max_attack_duration: float = 30.0
        self._kite_distance: int = 400
        self._last_cast_time: float = 0.0
        logger.info("CombatEngine initialized")

    @property
    def in_combat(self) -> bool:
        return self._combat_state not in (CombatState.IDLE, CombatState.LOOTING)

    def update(self, enemy_positions: list[tuple[int, int]]) -> bool:
        """Main combat loop tick. Called each frame.

        Args:
            enemy_positions: Detected enemy screen positions.

        Returns:
            True if combat is still active, False if area is clear.
        """
        # Update health and check for chicken
        self._health.update()
        needs_chicken = self._health.manage_potions()
        if needs_chicken:
            self._combat_state = CombatState.RETREATING
            return False

        targets = self._target_selector.evaluate_targets(enemy_positions)

        if not targets.has_targets:
            if self._combat_state != CombatState.IDLE:
                logger.info("Area cleared")
                self._combat_state = CombatState.IDLE
            return False

        # Timeout check
        elapsed = time.time() - self._attack_start_time
        if self._attack_start_time > 0 and elapsed > self._max_attack_duration:
            logger.warning("Combat timeout, disengaging")
            self._combat_state = CombatState.IDLE
            self._attack_start_time = 0.0
            return False

        self._combat_state = CombatState.ATTACKING
        if self._attack_start_time == 0.0:
            self._attack_start_time = time.time()

        self._execute_attack(targets)
        return True

    def _execute_attack(self, targets: TargetList) -> None:
        """Execute the appropriate attack pattern.

        Args:
            targets: Prioritized target list.
        """
        primary = targets.primary
        if primary is None:
            return

        # Check if we should kite
        if self._should_kite(targets):
            self._kite(primary.screen_x, primary.screen_y)
            return

        # Cast buffs if needed
        self._skills.cast_buffs()

        # Attack the primary target
        if primary.priority >= TargetPriority.HIGH:
            # Focus fire on high priority targets
            self._skills.cast_primary(primary.screen_x, primary.screen_y)
            time.sleep(0.2)
            # Double tap for bosses
            if primary.priority >= TargetPriority.BOSS:
                self._skills.cast_primary(primary.screen_x, primary.screen_y)
                time.sleep(0.3)
        else:
            # Normal attack pattern
            self._skills.cast_primary(primary.screen_x, primary.screen_y)
            time.sleep(0.15)

        # Use secondary skill if available and multiple targets exist
        if targets.count > 3 and self._char_config.secondary_skill is not None:
            second = targets.targets[1] if targets.count > 1 else primary
            self._skills.cast_secondary(second.screen_x, second.screen_y)
            time.sleep(0.2)

        self._last_cast_time = time.time()

    def _should_kite(self, targets: TargetList) -> bool:
        """Determine if the character should kite (move away from enemies).

        Kite when:
        - Health is below 50%
        - Too many enemies are very close
        - Character class is ranged

        Args:
            targets: Current target list.

        Returns:
            True if kiting is recommended.
        """
        if self._state.health_pct < 0.5:
            return True

        # Count very close enemies
        close_count = sum(
            1 for t in targets.targets
            if self._mouse.distance_to(t.screen_x, t.screen_y) < 200
        )
        if close_count >= 4:
            return True

        return False

    def _kite(self, enemy_x: int, enemy_y: int) -> None:
        """Move away from the nearest enemy.

        Args:
            enemy_x: Enemy screen X.
            enemy_y: Enemy screen Y.
        """
        self._combat_state = CombatState.KITING
        # Move in opposite direction of enemy relative to screen center
        center_x, center_y = 960, 540
        dx = center_x - enemy_x
        dy = center_y - enemy_y

        # Normalize and scale
        length = max(1, (dx * dx + dy * dy) ** 0.5)
        kite_x = center_x + int(dx / length * self._kite_distance)
        kite_y = center_y + int(dy / length * self._kite_distance)

        # Clamp to screen
        kite_x = max(100, min(kite_x, 1820))
        kite_y = max(100, min(kite_y, 980))

        # Teleport if available, otherwise click to move
        if self._char_config.teleport_key:
            self._skills.teleport(kite_x, kite_y)
        else:
            self._mouse.click(kite_x, kite_y)
            time.sleep(0.3)

        logger.debug("Kiting to (%d, %d)", kite_x, kite_y)
        self._combat_state = CombatState.ATTACKING

    def engage_boss(self, boss_x: int, boss_y: int) -> None:
        """Begin a boss encounter.

        Args:
            boss_x: Boss screen X position.
            boss_y: Boss screen Y position.
        """
        logger.info("Engaging boss at (%d, %d)", boss_x, boss_y)
        self._combat_state = CombatState.ENGAGING
        self._attack_start_time = time.time()
        self._max_attack_duration = 120.0  # Allow more time for bosses

        # Pre-buff
        self._skills.cast_buffs()
        time.sleep(0.5)

    def reset(self) -> None:
        """Reset combat state."""
        self._combat_state = CombatState.IDLE
        self._attack_start_time = 0.0
        self._max_attack_duration = 30.0
