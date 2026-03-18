"""Configuration management for D2R Autopilot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ScreenRegion(BaseModel):
    """Defines a rectangular region on screen."""

    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080


class HealthBarConfig(BaseModel):
    """Configuration for health/mana bar detection."""

    health_region: ScreenRegion = Field(
        default_factory=lambda: ScreenRegion(x=28, y=545, width=180, height=30)
    )
    mana_region: ScreenRegion = Field(
        default_factory=lambda: ScreenRegion(x=1710, y=545, width=180, height=30)
    )
    health_color_lower: tuple[int, int, int] = (0, 50, 50)
    health_color_upper: tuple[int, int, int] = (10, 255, 255)
    mana_color_lower: tuple[int, int, int] = (100, 50, 50)
    mana_color_upper: tuple[int, int, int] = (130, 255, 255)
    potion_threshold: float = 0.3
    chicken_threshold: float = 0.1


class ScreenConfig(BaseModel):
    """Screen capture and detection configuration."""

    monitor_index: int = 1
    game_region: ScreenRegion = Field(default_factory=ScreenRegion)
    health_bar: HealthBarConfig = Field(default_factory=HealthBarConfig)
    template_match_threshold: float = 0.8
    screenshot_delay: float = 0.05


class InputConfig(BaseModel):
    """Input simulation configuration."""

    mouse_move_speed: float = 0.1
    click_delay: float = 0.05
    key_press_delay: float = 0.03
    skill_cast_delay: float = 0.15
    failsafe_key: str = "f12"


class SkillBinding(BaseModel):
    """A skill and its key binding."""

    name: str
    key: str
    is_right_click: bool = False
    cooldown: float = 0.0
    aoe: bool = False
    range: int = 10


class CharacterConfig(BaseModel):
    """Character build configuration."""

    name: str = "default"
    character_class: str = "sorceress"
    primary_skill: SkillBinding = Field(
        default_factory=lambda: SkillBinding(
            name="Blizzard", key="f1", is_right_click=True, aoe=True
        )
    )
    secondary_skill: SkillBinding | None = None
    buff_skills: list[SkillBinding] = Field(default_factory=list)
    aura_skill: SkillBinding | None = None
    teleport_key: str = "f3"
    town_portal_key: str = "t"
    potion_keys: dict[str, str] = Field(
        default_factory=lambda: {"healing": "1", "mana": "2", "rejuv": "3"}
    )
    merc_enabled: bool = True


class LootRule(BaseModel):
    """A single loot filter rule."""

    name_pattern: str
    color: str = "any"
    quality: str = "any"
    pick_up: bool = True
    priority: int = 0


class LootConfig(BaseModel):
    """Loot filtering configuration."""

    enabled: bool = True
    pickup_radius: int = 300
    show_items_key: str = "alt"
    rules: list[LootRule] = Field(default_factory=lambda: [
        LootRule(name_pattern=".*Unique.*", color="gold", pick_up=True, priority=10),
        LootRule(name_pattern=".*Set.*", color="green", pick_up=True, priority=9),
        LootRule(name_pattern=".*Rune.*", pick_up=True, priority=8),
        LootRule(name_pattern=".*Charm.*", pick_up=True, priority=7),
        LootRule(name_pattern=".*Jewel.*", pick_up=True, priority=6),
        LootRule(name_pattern=".*Ring.*", color="gold", pick_up=True, priority=5),
        LootRule(name_pattern=".*Amulet.*", color="gold", pick_up=True, priority=5),
    ])
    stash_full_action: str = "stop"


class NavigationConfig(BaseModel):
    """Navigation and pathfinding configuration."""

    teleport_enabled: bool = True
    teleport_distance: int = 300
    stuck_timeout: float = 5.0
    movement_check_interval: float = 0.5
    minimap_region: ScreenRegion = Field(
        default_factory=lambda: ScreenRegion(x=1650, y=10, width=260, height=200)
    )


class RoutineConfig(BaseModel):
    """Farming routine configuration."""

    name: str = "mephisto"
    difficulty: str = "hell"
    max_game_time: float = 300.0
    min_game_time: float = 10.0
    chicken_on_death: bool = True
    repair_interval: int = 10
    stash_interval: int = 5
    resume_on_disconnect: bool = True


class BotConfig(BaseModel):
    """Root configuration for the bot."""

    screen: ScreenConfig = Field(default_factory=ScreenConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    character: CharacterConfig = Field(default_factory=CharacterConfig)
    loot: LootConfig = Field(default_factory=LootConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    routine: RoutineConfig = Field(default_factory=RoutineConfig)
    log_level: str = "INFO"
    run_count: int = 0
    max_runs: int = 0


def load_config(config_path: Path | None = None) -> BotConfig:
    """Load configuration from a YAML file, falling back to defaults."""
    if config_path is None:
        config_path = DEFAULT_CONFIG_DIR / "default.yaml"

    if config_path.exists():
        logger.info("Loading config from %s", config_path)
        with open(config_path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return BotConfig(**data)

    logger.info("No config file found at %s, using defaults", config_path)
    return BotConfig()


def save_config(config: BotConfig, config_path: Path) -> None:
    """Save configuration to a YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)
    logger.info("Config saved to %s", config_path)
