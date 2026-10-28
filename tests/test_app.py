import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from pacman.app import App, read_high_score, save_high_score
from pacman.engine import Phase
from pacman.rules import Direction


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = SimpleNamespace(scale=1, headless=True, mute=True, no_save=True,
                                  rng_rom=None, play=False, autoplay=False, title=True,
                                  seed=42, frames=1, screenshot=None)
        cls.app = App(options)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app.start(42)
        self.app.audio.muted = True
        self.app.options.headless = True
        self.app.running = True
        pygame.event.clear()

    def key(self, key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
        for event in pygame.event.get():
            self.app._event(event)

    def test_enter_from_sdl_event_queue_starts_the_game(self):
        self.app.game = None
        self.key(pygame.K_RETURN)
        self.assertIsNotNone(self.app.game)
        self.assertEqual(self.app.game.seed, 42)
        self.assertEqual(self.app.game.phase, Phase.READY)

    def test_space_also_starts_from_title(self):
        self.app.game = None
        self.key(pygame.K_SPACE)
        self.assertIsNotNone(self.app.game)

    def test_arrow_and_wasd_feed_the_actual_player_controller(self):
        self.key(pygame.K_UP)
        self.assertEqual(self.app.game.wanted, Direction.UP)
        self.key(pygame.K_a)
        self.assertEqual(self.app.game.wanted, Direction.LEFT)
        self.key(pygame.K_d)
        self.assertEqual(self.app.game.wanted, Direction.RIGHT)

    def test_pause_freezes_simulation_and_resume_restarts_it(self):
        game = self.app.game
        self.key(pygame.K_p)
        for _ in range(60):
            self.app._tick()
        self.assertEqual(game.ticks, 0)
        self.key(pygame.K_p)
        self.app._tick()
        self.assertEqual(game.ticks, 1)

    def test_new_game_changes_maze_and_resets_score(self):
        old_floors = self.app.game.maze.floors
        self.app.game.score = 1000
        with patch("pacman.app.secrets.randbits", return_value=12345):
            self.key(pygame.K_r)
        self.assertEqual(self.app.game.score, 0)
        self.assertEqual(self.app.game.seed, 12345)
        self.assertNotEqual(self.app.game.maze.floors, old_floors)

    def test_help_on_title_returns_to_title_without_starting(self):
        self.app.game = None
        self.key(pygame.K_F1)
        self.assertTrue(self.app.help_open)
        self.key(pygame.K_RETURN)
        self.assertFalse(self.app.help_open)
        self.assertFalse(self.app.paused)
        self.assertIsNone(self.app.game)

    def test_losing_window_focus_auto_pauses_active_game(self):
        self.app.game.phase = Phase.PLAYING
        self.app.options.headless = False
        self.app._event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertTrue(self.app.paused)

    def test_audio_toggle_and_synthesized_chomp(self):
        self.assertTrue(self.app.audio.available)
        self.key(pygame.K_m)
        self.assertFalse(self.app.audio.muted)
        self.app.audio.play("dot")
        self.assertIsNotNone(pygame.mixer.Channel(1).get_sound())
        self.key(pygame.K_m)
        self.assertTrue(self.app.audio.muted)
        self.assertFalse(pygame.mixer.Channel(1).get_busy())

    def test_q_quits(self):
        self.key(pygame.K_q)
        self.assertFalse(self.app.running)


class PersistenceTests(unittest.TestCase):
    def test_high_score_atomic_round_trip_and_corrupt_file_recovery(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory) / "score.json"
            self.assertTrue(path.resolve().is_relative_to(root))
            self.assertEqual(read_high_score(path), 0)
            save_high_score(12340, path)
            self.assertEqual(read_high_score(path), 12340)
            self.assertFalse(path.with_suffix(".tmp").exists())
            for value in ("bad json", "[]", json.dumps({"high_score": -1}),
                          json.dumps({"high_score": True})):
                path.write_text(value, encoding="utf-8")
                self.assertEqual(read_high_score(path), 0)


if __name__ == "__main__":
    unittest.main()
