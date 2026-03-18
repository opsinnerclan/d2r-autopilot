"""Skill management and casting module."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2r_autopilot.config import CharacterConfig, SkillBinding
    from d2r_autopilot.input.keyboard import KeyboardController
    from d2r_autopilot.input.mouse import MouseController

logger = logging.getLogger(__name__)


class SkillManager:
    """Manages skill selection, casting, and buff maintenance."""

    def __init__(
        self,
        config: CharacterConfig,
        keyboard: KeyboardController,
        mouse: MouseController,
    ) -> None:
        self._config = config
        self._keyboard = keyboard
        self._mouse = mouse
        self._active_right_skill: str = ""
        self._active_left_skill: str = ""
        self._buff_timers: dict[str, float] = {}
        self._skill_cooldowns: dict[str, float] = {}
        logger.info("SkillManager initialized (class=%s)", config.character_class)

    def select_skill(self, skill: SkillBinding) -> None:
        """Select a skill by pressing its hotkey.

        Args:
            skill: The skill binding to select.
        """
        self._keyboard.press(skill.key)
        time.sleep(0.05)

        if skill.is_right_click:
            self._active_right_skill = skill.name
        else:
            self._active_left_skill = skill.name
        logger.debug("Selected skill: %s (key=%s)", skill.name, skill.key)

    def cast_primary(self, target_x: int, target_y: int) -> None:
        """Cast the primary skill at a target location.

        Args:
            target_x: Screen X coordinate.
            target_y: Screen Y coordinate.
        """
        skill = self._config.primary_skill
        self.select_skill(skill)

        if skill.is_right_click:
            self._mouse.right_click(target_x, target_y)
        else:
            self._mouse.click(target_x, target_y)

        self._skill_cooldowns[skill.name] = time.time()
        logger.debug("Cast %s at (%d, %d)", skill.name, target_x, target_y)

    def cast_secondary(self, target_x: int, target_y: int) -> None:
        """Cast the secondary skill at a target location.

        Args:
            target_x: Screen X coordinate.
            target_y: Screen Y coordinate.
        """
        if self._config.secondary_skill is None:
            return

        skill = self._config.secondary_skill
        self.select_skill(skill)

        if skill.is_right_click:
            self._mouse.right_click(target_x, target_y)
        else:
            self._mouse.click(target_x, target_y)

        self._skill_cooldowns[skill.name] = time.time()
        logger.debug("Cast %s at (%d, %d)", skill.name, target_x, target_y)

    def cast_buffs(self) -> None:
        """Cast all buff skills that need refreshing.

        Buffs are cast on self (at character center) and tracked with timers.
        """
        screen_center_x = 960  # 1920/2
        screen_center_y = 540  # 1080/2

        for buff in self._config.buff_skills:
            last_cast = self._buff_timers.get(buff.name, 0.0)
            if (time.time() - last_cast) < buff.cooldown:
                continue

            self.select_skill(buff)
            if buff.is_right_click:
                self._mouse.right_click(screen_center_x, screen_center_y)
            else:
                self._mouse.click(screen_center_x, screen_center_y)

            self._buff_timers[buff.name] = time.time()
            time.sleep(0.3)
            logger.info("Cast buff: %s", buff.name)

        # Restore primary skill after buffing
        self.select_skill(self._config.primary_skill)

    def teleport(self, target_x: int, target_y: int) -> None:
        """Use teleport skill to move to a location.

        Args:
            target_x: Screen X coordinate.
            target_y: Screen Y coordinate.
        """
        self._keyboard.press(self._config.teleport_key)
        time.sleep(0.05)
        self._mouse.right_click(target_x, target_y)
        time.sleep(0.15)
        logger.debug("Teleported to (%d, %d)", target_x, target_y)

    def cast_town_portal(self) -> None:
        """Open a Town Portal."""
        self._keyboard.press(self._config.town_portal_key)
        time.sleep(1.5)
        logger.info("Cast Town Portal")

    def is_on_cooldown(self, skill_name: str, cooldown: float) -> bool:
        """Check if a skill is on cooldown.

        Args:
            skill_name: Name of the skill.
            cooldown: Cooldown duration in seconds.

        Returns:
            True if the skill is still on cooldown.
        """
        last_use = self._skill_cooldowns.get(skill_name, 0.0)
        return (time.time() - last_use) < cooldown
