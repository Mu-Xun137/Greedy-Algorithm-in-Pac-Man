"""Capture the real menu flow and a live target overlay using SDL events."""

import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from pacman.app import App
from pacman.engine import Phase
from pacman.rules import GhostState
from pacman.video import SCREEN


def main():
    options = SimpleNamespace(scale=1, headless=True, mute=True, no_save=True,
                              rng_rom=None, play=False, autoplay=False, title=True,
                              seed=42, frames=1, screenshot=None)
    app = App(options)
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)

    def tap(key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
        for event in pygame.event.get():
            app._event(event)

    def capture(name):
        canvas = app._draw()
        path = output / name
        pygame.image.save(pygame.transform.scale(canvas, (SCREEN[0] * 3, SCREEN[1] * 3)), str(path))
        print(path.name)

    try:
        capture("title.png")
        tap(pygame.K_c)
        capture("customization.png")
        tap(pygame.K_RETURN)
        capture("ghost_selection.png")
        tap(pygame.K_RETURN)
        assert app.notice is not None
        capture("ghost_dependency.png")
        tap(pygame.K_RETURN)  # Acknowledge, without accidentally toggling again.
        tap(pygame.K_RETURN)  # Re-enable red; blue remains off.
        tap(pygame.K_DOWN)
        tap(pygame.K_DOWN)
        tap(pygame.K_RETURN)  # Re-enable blue now that red exists.
        tap(pygame.K_ESCAPE)
        tap(pygame.K_DOWN)
        tap(pygame.K_RETURN)  # Enable target overlay.
        capture("customization_targets.png")
        tap(pygame.K_ESCAPE)
        tap(pygame.K_RETURN)
        options.autoplay = True
        for tick in range(1, 6001):
            app._tick()
            game = app.game
            if (game.phase == Phase.PLAYING and not game.fright_left and not game.freeze_ticks
                    and all(g.state == GhostState.ROAMING for g in game.active_ghosts)):
                capture("targets.png")
                print(f"live targets: seed={game.seed} tick={tick} score={game.score}")
                break
        else:
            raise AssertionError("No live four-ghost target frame found")
        tap(pygame.K_p)
        capture("paused.png")
        tap(pygame.K_F1)
        capture("help.png")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
