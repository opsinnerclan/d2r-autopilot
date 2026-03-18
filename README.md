# D2R Autopilot

Automatic player bot for Diablo 2 Resurrected. Uses screen capture, OpenCV template matching, and input simulation to automate farming runs.

> **Disclaimer:** Using this bot in online play violates Blizzard's Terms of Service. Use at your own risk. This project is for educational purposes.

## Features

- **Screen Capture & Recognition** — Fast screen capture via `mss`, template matching and color detection via OpenCV, OCR for item name reading
- **Health & Mana Monitoring** — Reads health/mana orbs in real-time, automatic potion usage, emergency "chicken" (quit game) when health is critical
- **Combat Engine** — Priority-based target selection, skill rotation with cooldown tracking, automatic kiting for ranged characters, buff maintenance
- **Navigation** — Minimap-based pathfinding, teleport support, stuck detection and recovery, area exit/entrance detection
- **Loot System** — Configurable loot filter rules by item name, color, and quality, automatic pickup sorted by priority, inventory management and stashing
- **Farming Routines** — Mephisto (Act 3), Chaos Sanctuary / Diablo (Act 4), Baal (Act 5)
- **Configuration** — YAML-based configs, per-build character profiles, CLI overrides

## Requirements

- Python 3.10+
- Windows (for game interaction via pyautogui)
- Diablo 2 Resurrected running in windowed/borderless mode at 1920x1080
- Tesseract OCR installed (optional, for item name reading)

## Installation

```bash
# Clone the repo
git clone https://github.com/your-username/d2r-autopilot.git
cd d2r-autopilot

# Install with pip
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# Generate a default config file
d2r-autopilot --generate-config config/my_config.yaml

# Edit the config to match your setup (key bindings, screen regions, etc.)

# Run with default settings (Blizzard Sorc, Mephisto runs)
d2r-autopilot

# Run with a specific config
d2r-autopilot -c config/builds/sorceress_blizzard.yaml

# Run Chaos Sanctuary with a Hammerdin
d2r-autopilot -c config/builds/paladin_hammerdin.yaml --routine chaos

# Run 50 Baal runs
d2r-autopilot --routine baal --max-runs 50

# Debug mode
d2r-autopilot --log-level DEBUG
```

## Configuration

Configuration is YAML-based. See `config/default.yaml` for all options.

### Key Sections

| Section | Description |
|---------|-------------|
| `screen` | Monitor index, game region, health bar detection regions |
| `input` | Mouse speed, click delays, failsafe key |
| `character` | Class, skill bindings, potion keys, buff setup |
| `loot` | Pickup rules, item filters by name/color/quality |
| `navigation` | Teleport settings, stuck detection |
| `routine` | Which routine to run, difficulty, timeouts |

### Character Builds

Pre-built configs are in `config/builds/`:

- `sorceress_blizzard.yaml` — Blizzard Sorc for Mephisto/AT farming
- `paladin_hammerdin.yaml` — Hammerdin for Chaos/Baal runs

### Loot Filter Rules

```yaml
loot:
  rules:
    - name_pattern: ".*"          # Match any item name
      color: gold                  # Gold = Unique items
      pick_up: true
      priority: 10                 # Higher = picked up first
    - name_pattern: ".*Rune$"
      pick_up: true
      priority: 8
```

## Architecture

```
src/d2r_autopilot/
├── __main__.py          # CLI entry point
├── bot.py               # Main bot controller & game loop
├── config.py            # Pydantic configuration models
├── screen/
│   ├── capture.py       # Screen capture (mss)
│   ├── detector.py      # Template matching & color detection (OpenCV)
│   └── ocr.py           # Text recognition (Tesseract)
├── input/
│   ├── keyboard.py      # Keyboard simulation
│   └── mouse.py         # Mouse simulation with human-like movement
├── game/
│   ├── state.py         # Game state tracking (screen, location, stats)
│   ├── health.py        # Health/mana monitoring & potion management
│   ├── inventory.py     # Inventory slot tracking & stashing
│   ├── map_reader.py    # Minimap reading & position tracking
│   └── skills.py        # Skill selection, casting & buff management
├── combat/
│   ├── engine.py        # Combat loop, kiting, attack patterns
│   └── targeting.py     # Target priority & selection
├── navigation/
│   ├── pathfinder.py    # Movement, teleporting, stuck recovery
│   └── town.py          # Town NPC interaction, repair, stash
├── loot/
│   ├── filter.py        # Loot rule evaluation & filtering
│   └── picker.py        # Ground item detection & pickup
└── routines/
    ├── base.py          # Abstract base routine class
    ├── mephisto.py      # Mephisto farming (Act 3)
    ├── chaos.py         # Chaos Sanctuary / Diablo (Act 4)
    └── baal.py          # Baal runs (Act 5)
```

## How It Works

1. **Game Loop**: The bot creates games, executes a farming routine, exits, and repeats
2. **Screen Reading**: Captures the game screen ~20 times/sec, uses template matching to detect game state (menus, HUD elements) and color detection for health/mana orbs
3. **Navigation**: Reads the minimap to find the player position, exits, and enemies. Uses teleport or click-to-move to navigate
4. **Combat**: Detects enemies on the minimap, selects targets by priority/distance, casts skills, manages buffs, and kites when health is low
5. **Looting**: After combat, presses Alt to show item labels, detects colored text labels, reads item names via OCR, filters by rules, and clicks to pick up
6. **Town Management**: Returns to town via TP, visits NPCs for repairs, stashes items, buys potions

## Extending

### Adding a New Routine

1. Create a new file in `src/d2r_autopilot/routines/`
2. Subclass `BaseRoutine` and implement: `town_prep()`, `navigate()`, `clear()`, `boss_fight()`
3. Register it in `Bot._create_routine()` in `bot.py`

### Adding a New Character Build

1. Create a YAML file in `config/builds/`
2. Set skill bindings, buff timers, and potion keys
3. Run with: `d2r-autopilot -c config/builds/your_build.yaml`

## License

MIT
