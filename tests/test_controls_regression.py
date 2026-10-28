"""Regressions through the same SDL event queue consumed by the window loop."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from pacman.app import App
from pacman.engine import Phase


class ControlsRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = SimpleNamespace(scale=1, headless=True, mute=True, no_save=True,
                                  rng_rom=None, play=False, autoplay=False, title=True,
                                  seed=None, frames=1, screenshot=None)
        cls.app = App(options)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app.start(42)
        pygame.event.clear()

    def key(self, key, repeat=False):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, repeat=repeat))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
        for event in pygame.event.get():
            self.app._event(event)

    def test_game_over_enter_restarts_with_help_open(self):
        previous = self.app.game
        previous.phase = Phase.GAME_OVER
        self.key(pygame.K_F1)
        self.key(pygame.K_RETURN)
        self.assertIsNot(self.app.game, previous, "one Enter must restart even with an overlay open")

    def test_enter_during_last_death_restarts_without_waiting(self):
        previous = self.app.game
        previous.lives = 1
        previous.phase = Phase.DYING
        previous.phase_ticks = 30
        self.key(pygame.K_RETURN)
        self.assertIsNot(self.app.game, previous, "the final death animation must not swallow Enter")

    def test_restarting_cannot_reuse_previous_geometry(self):
        previous = self.app.game.maze.floors
        self.app.game.phase = Phase.GAME_OVER
        with patch("pacman.app.secrets.randbits", return_value=42):
            self.key(pygame.K_RETURN)
        self.assertTrue(self.app.game.maze.floors != previous, "new run reused the previous maze geometry")

    def test_held_pause_key_does_not_immediately_unpause(self):
        self.key(pygame.K_p)
        self.assertTrue(self.app.paused)
        self.key(pygame.K_p, repeat=True)
        self.assertTrue(self.app.paused)

    def test_held_help_key_does_not_immediately_close_help(self):
        self.key(pygame.K_F1)
        self.assertTrue(self.app.help_open)
        self.key(pygame.K_F1, repeat=True)
        self.assertTrue(self.app.help_open)

    def test_starting_with_r_cannot_leave_an_old_initial_seed_for_later(self):
        self.app._to_title()
        self.app._initial_seed = 42
        self.key(pygame.K_r)
        previous = self.app.game.maze.floors
        self.assertIsNone(self.app._initial_seed)
        self.app._to_title()
        with patch("pacman.app.secrets.randbits", return_value=42):
            self.key(pygame.K_RETURN)
        self.assertTrue(self.app.game.maze.floors != previous)


if __name__ == "__main__":
    unittest.main()
