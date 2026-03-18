"""CLI entry point for D2R Autopilot."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

from d2r_autopilot import __version__
from d2r_autopilot.bot import Bot
from d2r_autopilot.config import BotConfig, load_config, save_config


def setup_logging(level: str) -> None:
    """Configure logging for the application."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("d2r_autopilot.log", mode="a"),
        ],
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="d2r-autopilot",
        description="Diablo 2 Resurrected automatic player bot",
    )
    parser.add_argument(
        "--version", action="version", version=f"d2r-autopilot {__version__}"
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--routine",
        choices=["mephisto", "chaos", "baal"],
        default=None,
        help="Farming routine to run (overrides config)",
    )
    parser.add_argument(
        "--character",
        choices=["sorceress", "paladin", "amazon", "necromancer", "barbarian", "druid", "assassin"],
        default=None,
        help="Character class (overrides config)",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Maximum number of runs (0 = unlimited)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["normal", "nightmare", "hell"],
        default=None,
        help="Game difficulty (overrides config)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging level",
    )
    parser.add_argument(
        "--generate-config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Generate a default config file at the given path and exit",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Generate config mode
    if args.generate_config is not None:
        config = BotConfig()
        save_config(config, args.generate_config)
        print(f"Default config written to {args.generate_config}")
        return

    # Load config
    config = load_config(args.config)

    # Apply CLI overrides
    if args.routine is not None:
        config.routine.name = args.routine
    if args.character is not None:
        config.character.character_class = args.character
    if args.max_runs is not None:
        config.max_runs = args.max_runs
    if args.difficulty is not None:
        config.routine.difficulty = args.difficulty
    if args.log_level is not None:
        config.log_level = args.log_level

    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("D2R Autopilot v%s starting", __version__)
    logger.info("Routine: %s | Class: %s | Difficulty: %s",
                config.routine.name, config.character.character_class, config.routine.difficulty)

    # Create and start bot
    bot = Bot(config)

    # Handle graceful shutdown
    def signal_handler(sig: int, frame: object) -> None:
        logger.info("Shutdown signal received")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bot
    print("\n" + "=" * 60)
    print("  D2R Autopilot - Automatic Player Bot")
    print(f"  Routine: {config.routine.name}")
    print(f"  Class: {config.character.character_class}")
    print(f"  Max Runs: {config.max_runs or 'Unlimited'}")
    print("=" * 60)
    print("\nPress Ctrl+C or F12 to stop\n")

    bot.start()


if __name__ == "__main__":
    main()
