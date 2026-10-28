import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from pacman.app import App
from pacman.customization import Customization
from pacman.engine import Phase
from pacman.maze import generate
from pacman.rules import GhostKind as K, GhostState as S
from pacman.rules import Direction
from pacman.video import BLUE, COLORS, MAZE_Y, SCREEN, YELLOW, dashed_line


class CustomizationUITests(unittest.TestCase):
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
        self.app.customization = Customization()
        self.app.targets = False
        self.app.start(42)
        self.app._held_keys.clear()
        pygame.event.clear()

    def key(self, key=0, **fields):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, **fields))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, **fields))
        for event in pygame.event.get():
            self.app._event(event)

    def click(self, action):
        self.app._draw()
        rect = self.app.renderer.buttons[action]
        viewport = self.app._viewport()
        point = (int(viewport.x + rect.centerx * viewport.width / SCREEN[0]),
                 int(viewport.y + rect.centery * viewport.height / SCREEN[1]))
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        for event in pygame.event.get():
            self.app._event(event)

    def test_entire_custom_menu_is_operable_by_keyboard(self):
        self.key(pygame.K_c)
        self.key(pygame.K_RETURN)
        self.assertEqual(self.app.custom_page, "ghosts")
        self.key(pygame.K_RETURN)
        self.assertIsNotNone(self.app.notice)
        self.assertEqual({g.kind for g in self.app.game.active_ghosts}, {K.PINKY, K.CLYDE})
        self.key(pygame.K_RETURN)
        self.assertIsNone(self.app.notice)
        self.assertEqual(self.app.custom_page, "ghosts")
        self.key(pygame.K_ESCAPE)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_RETURN)
        self.assertTrue(self.app.targets)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_RETURN)
        self.assertFalse(self.app.customization.show_roles)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_RETURN)
        self.assertFalse(self.app.custom_open)
        self.assertFalse(self.app.paused)

    def test_scaled_letterboxed_mouse_coordinates_open_customization(self):
        self.app.window = pygame.display.set_mode((500, 400), pygame.RESIZABLE)
        self.click("custom")
        self.assertTrue(self.app.custom_open)
        self.click("choice:0")
        self.assertEqual(self.app.custom_page, "ghosts")
        self.click("choice:0")
        self.assertIn("同时关闭蓝鬼", self.app.notice)
        self.click("notice_ok")
        self.assertIsNone(self.app.notice)

    def test_target_toggle_persists_through_new_game(self):
        self.key(pygame.K_F3)
        self.app.start(123)
        self.assertTrue(self.app.targets)
        self.assertTrue(self.app.customization.show_targets)

    def test_settings_changes_are_saved_from_menu(self):
        self.key(pygame.K_c)
        self.app.options.no_save = False
        try:
            with patch("pacman.app.save_customization") as save:
                self.app._custom_choice(1)
                save.assert_called_once_with(self.app.customization)
        finally:
            self.app.options.no_save = True

    def test_customization_pauses_game_and_restores_prior_pause_state(self):
        game = self.app.game
        self.key(pygame.K_c)
        for _ in range(5):
            self.app._tick()
        self.assertEqual(game.ticks, 0)
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.paused)
        self.key(pygame.K_p)
        self.key(pygame.K_c)
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.paused)

    def test_physical_p_and_f1_work_when_key_symbol_is_missing(self):
        self.key(scancode=pygame.KSCAN_P)
        self.assertTrue(self.app.paused)
        self.key(scancode=pygame.KSCAN_P)
        self.assertFalse(self.app.paused)
        self.key(scancode=pygame.KSCAN_F1)
        self.assertTrue(self.app.help_open)

    def test_caps_and_shift_letter_symbols_are_normalized(self):
        self.key(ord("P"), unicode="P", scancode=pygame.KSCAN_P)
        self.assertTrue(self.app.paused)

    def test_duplicate_keydown_cannot_toggle_twice_before_release(self):
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)
        self.app._event(event)
        self.app._event(event)
        self.assertTrue(self.app.paused)
        self.app._event(pygame.event.Event(pygame.KEYUP, key=pygame.K_p))
        self.key(pygame.K_p)
        self.assertFalse(self.app.paused)

    def test_pause_key_resumes_directly_even_from_help_over_pause(self):
        self.key(pygame.K_p)
        self.key(pygame.K_F1)
        self.key(pygame.K_p)
        self.assertFalse(self.app.help_open)
        self.assertFalse(self.app.paused)

    def test_game_over_mouse_restart_matches_enter_even_with_help(self):
        previous = self.app.game
        previous.phase = Phase.GAME_OVER
        self.key(pygame.K_F1)
        self.click("restart")
        self.assertIsNot(self.app.game, previous)
        self.assertEqual(self.app.game.phase, Phase.PLAYING)

    def test_title_help_has_two_separately_clickable_close_buttons(self):
        self.app._to_title()
        self.key(pygame.K_F1)
        self.app._draw()
        self.assertIn("resume", self.app.renderer.buttons)
        self.assertIn("close_help", self.app.renderer.buttons)
        self.click("resume")
        self.assertFalse(self.app.help_open)

    def test_live_target_formula_is_not_stuck_on_last_decision(self):
        game = self.app.game
        game.clock.phase = 1
        game.player.x, game.player.y = 84, 84
        game.ghosts[K.BLINKY].target = (-100, -100)
        markers = self.app.renderer.draw_targets(game)
        self.assertIn((COLORS[K.BLINKY], (84, 108)), markers)
        game.player.x += 8
        self.assertIn((COLORS[K.BLINKY], (92, 108)), self.app.renderer.draw_targets(game))

    def test_targets_are_not_fabricated_for_frightened_or_returning_ghosts(self):
        game = self.app.game
        ghost = game.ghosts[K.BLINKY]
        ghost.frightened = True
        self.assertIsNone(game.visible_target(ghost))
        ghost.frightened = False
        ghost.state = S.EYES
        self.assertIsNone(game.visible_target(ghost))

    def test_inky_construction_joins_blinky_pivot_and_target_in_inkys_color(self):
        game = self.app.game
        game.clock.phase = 1
        game.player.x, game.player.y = 84, 84
        game.player.direction = Direction.RIGHT
        game.ghosts[K.BLINKY].x, game.ghosts[K.BLINKY].y = 36, 36
        game.ghosts[K.INKY].state = S.ROAMING
        self.assertEqual(game.inky_construction(), ((4, 4), (12, 10), (20, 16)))
        with patch("pacman.video.dashed_line", wraps=dashed_line) as draw:
            self.app.renderer.draw_targets(game)
        lines = {(call.args[2], call.args[3]) for call in draw.call_args_list
                 if call.args[1] == COLORS[K.INKY]}
        self.assertIn(((36, 60), (100, 108)), lines)
        self.assertIn(((100, 108), (164, 156)), lines)
        self.assertIn(((84, 108), (100, 108)), lines)
        self.assertEqual(self.app.renderer.inky_pivot, (100, 108))

    def test_inky_has_no_blinky_construction_during_scatter_or_fright(self):
        game = self.app.game
        game.ghosts[K.INKY].state = S.ROAMING
        self.assertIsNone(game.inky_construction())
        game.clock.phase = 1
        game.ghosts[K.INKY].frightened = True
        self.assertIsNone(game.inky_construction())
        game.ghosts[K.INKY].frightened = False
        game.set_enabled_ghosts({K.BLINKY})
        self.assertIsNone(game.inky_construction())

    def test_marker_is_hollow_and_drawn_visibly_over_player(self):
        game = self.app.game
        game.clock.phase = 1
        game.player.x, game.player.y = 84, 84
        canvas = self.app.renderer.draw_game(game, 0, True)
        self.assertEqual(canvas.get_at((88, 108))[:3], COLORS[K.BLINKY])
        self.assertEqual(canvas.get_at((84, 108))[:3], YELLOW)

    def test_dashed_line_has_regular_visible_gaps(self):
        surface = pygame.Surface((64, 10))
        surface.fill((0, 0, 0))
        dashed_line(surface, BLUE, (0, 5), (50, 5))
        self.assertTrue(all(surface.get_at((x, 5))[:3] == BLUE for x in (0, 1, 2, 6, 7, 8)))
        self.assertTrue(all(surface.get_at((x, 5))[:3] == (0, 0, 0) for x in (3, 4, 5, 9, 10, 11)))

    def test_removed_ghost_is_not_drawn(self):
        game = self.app.game
        game.set_enabled_ghosts([])
        with patch("pacman.video.ghost") as draw_ghost:
            self.app.renderer.draw_game(game, 0)
            draw_ghost.assert_not_called()

    def test_wall_cache_tracks_geometry_even_with_reused_seed_metadata(self):
        game = self.app.game
        renderer = self.app.renderer
        renderer.draw_game(game, 0)
        before = pygame.image.tobytes(renderer.walls, "RGB")
        game.maze = generate(43)
        game.maze.seed = 42
        renderer.draw_game(game, 0)
        self.assertNotEqual(pygame.image.tobytes(renderer.walls, "RGB"), before)


if __name__ == "__main__":
    unittest.main()
