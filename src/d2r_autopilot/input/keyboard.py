"""Keyboard input simulation for D2R."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import pyautogui

if TYPE_CHECKING:
    from d2r_autopilot.config import InputConfig

logger = logging.getLogger(__name__)

# Disable pyautogui failsafe (we handle our own)
pyautogui.FAILSAFE = False


class KeyboardController:
    """Simulates keyboard input for game control."""

    def __init__(self, config: InputConfig) -> None:
        self._config = config
        self._key_states: dict[str, bool] = {}
        self._last_press_time: dict[str, float] = {}
        pyautogui.PAUSE = config.key_press_delay
        logger.info("KeyboardController initialized")

    def press(self, key: str) -> None:
        """Press and release a key.

        Args:
            key: Key name (e.g., 'f1', 'a', 'shift').
        """
        pyautogui.press(key)
        self._last_press_time[key] = time.time()
        logger.debug("Key press: %s", key)

    def hold(self, key: str) -> None:
        """Hold a key down.

        Args:
            key: Key name to hold.
        """
        if not self._key_states.get(key, False):
            pyautogui.keyDown(key)
            self._key_states[key] = True
            logger.debug("Key hold: %s", key)

    def release(self, key: str) -> None:
        """Release a held key.

        Args:
            key: Key name to release.
        """
        if self._key_states.get(key, False):
            pyautogui.keyUp(key)
            self._key_states[key] = False
            logger.debug("Key release: %s", key)

    def release_all(self) -> None:
        """Release all currently held keys."""
        for key in list(self._key_states.keys()):
            if self._key_states[key]:
                self.release(key)
        logger.debug("All keys released")

    def hotkey(self, *keys: str) -> None:
        """Press a key combination.

        Args:
            keys: Keys to press simultaneously (e.g., 'ctrl', 'v').
        """
        pyautogui.hotkey(*keys)
        logger.debug("Hotkey: %s", "+".join(keys))

    def type_text(self, text: str, interval: float = 0.05) -> None:
        """Type a string of text.

        Args:
            text: Text to type.
            interval: Delay between each character.
        """
        pyautogui.typewrite(text, interval=interval)
        logger.debug("Typed text: %s", text)

    def can_press(self, key: str, cooldown: float) -> bool:
        """Check if enough time has passed since last press.

        Args:
            key: Key name.
            cooldown: Minimum seconds between presses.

        Returns:
            True if the cooldown has elapsed.
        """
        last_time = self._last_press_time.get(key, 0.0)
        return (time.time() - last_time) >= cooldown

    def press_skill(self, skill_key: str, cooldown: float = 0.0) -> bool:
        """Press a skill key if cooldown allows.

        Args:
            skill_key: The key bound to the skill.
            cooldown: Minimum time between uses.

        Returns:
            True if the skill was cast.
        """
        if not self.can_press(skill_key, cooldown):
            return False
        self.press(skill_key)
        time.sleep(self._config.skill_cast_delay)
        return True

    def use_potion(self, potion_key: str) -> None:
        """Use a potion by pressing its belt key.

        Args:
            potion_key: Key for the potion slot (e.g., '1', '2', '3', '4').
        """
        self.press(potion_key)
        logger.info("Used potion: key=%s", potion_key)
