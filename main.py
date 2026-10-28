"""Run the game: python main.py. See --help for reproducible capture tools."""

import argparse
import os
from pathlib import Path
import sys


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="Classic Python PAC-MAN with a new maze every game.")
    parser.add_argument("--seed", type=lambda value: int(value, 0), help="replay a map, e.g. 42 or 0x2A")
    parser.add_argument("--scale", type=positive, default=3, help="initial integer pixel scale (default: 3)")
    parser.add_argument("--mute", action="store_true", help="start with sound muted")
    parser.add_argument("--no-save", action="store_true", help="do not read or write local high scores")
    parser.add_argument("--headless", action="store_true", help="run a finite simulation using SDL dummy devices")
    parser.add_argument("--frames", type=positive, help="exit after N rendered frames (headless default: 600)")
    parser.add_argument("--screenshot", type=Path, help="save a 3x PNG of the final frame")
    parser.add_argument("--autoplay", action="store_true", help="demonstration joystick; starts a game")
    screens = parser.add_mutually_exclusive_group()
    screens.add_argument("--play", action="store_true", help="start immediately, skipping the title")
    screens.add_argument("--title", action="store_true", help="stay on the title screen for a capture")
    screens.add_argument("--learn", action="store_true", help="open the animated greedy-algorithm lessons")
    parser.add_argument("--rng-rom", type=Path,
                        help="optional 8192+ byte memory dump or directory with pacman.6e / pacman.6f")
    options = parser.parse_args()
    if options.title and options.autoplay:
        parser.error("--title and --autoplay cannot be combined")
    if options.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        options.frames = options.frames or 600
        options.no_save = True
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        from pacman.app import App
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        print("Missing pygame-ce. Run: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    try:
        return App(options).run()
    except (OSError, ValueError) as exc:
        print(f"Cannot start game: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
