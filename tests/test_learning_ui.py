import os
from types import SimpleNamespace
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from pacman.app import App
from pacman.learning import LESSONS, LearningPlayer, sample_lesson
from pacman.learning_view import detail_lines
from pacman.rules import GhostKind
from pacman.video import Renderer, SCREEN, WHITE, ui_image


class FontLifecycleTests(unittest.TestCase):
    def test_recreated_renderer_does_not_reuse_invalid_fonts(self):
        try:
            pygame.init()
            pygame.display.set_mode(SCREEN)
            Renderer().draw_learning(LearningPlayer())
            pygame.quit()
            pygame.init()
            pygame.display.set_mode(SCREEN)
            image = Renderer().draw_learning(LearningPlayer(index=4, details_open=True))
            self.assertEqual(image.get_size(), SCREEN)
        finally:
            pygame.quit()


class LearningUITests(unittest.TestCase):
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
        self.app.learning = LearningPlayer()
        self.app._held_keys.clear()
        self.app.running = True
        pygame.event.clear()

    def key(self, key=0, **fields):
        for kind in (pygame.KEYDOWN, pygame.KEYUP):
            pygame.event.post(pygame.event.Event(kind, key=key, **fields))
        for event in pygame.event.get():
            self.app._event(event)

    def click(self, action):
        self.app._draw()
        rect = self.app.renderer.buttons[action]
        viewport = self.app._viewport()
        point = (round(viewport.x + rect.centerx * viewport.width / SCREEN[0]),
                 round(viewport.y + rect.centery * viewport.height / SCREEN[1]))
        self.app._event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))

    def test_title_has_a_separate_learning_entry(self):
        self.app._to_title()
        self.click("learn")
        self.assertTrue(self.app.learning_open)
        self.assertIsNone(self.app.game)
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.learning_open)
        self.assertFalse(self.app.paused)
        self.assertTrue(self.app.running)

    def test_title_keyboard_can_select_the_third_entry(self):
        self.app._to_title()
        self.key(pygame.K_DOWN)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_RETURN)
        self.assertTrue(self.app.learning_open)
        self.assertIsNone(self.app.game)

    def test_game_freezes_while_the_lesson_animation_advances(self):
        game = self.app.game
        self.key(scancode=pygame.KSCAN_L)
        for _ in range(100):
            self.app._tick()
        self.assertEqual(game.ticks, 0)
        self.assertEqual(self.app.learning.frame, 100)
        self.key(pygame.K_ESCAPE)
        self.assertIs(self.app.game, game)
        self.assertFalse(self.app.paused)

    def test_previously_paused_game_stays_paused_after_learning(self):
        self.key(pygame.K_p)
        self.key(pygame.K_l)
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.paused)

    def test_learning_returns_to_the_help_screen_that_opened_it(self):
        self.key(pygame.K_F1)
        self.click("learn")
        self.assertFalse(self.app.help_open)
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.help_open)
        self.assertTrue(self.app.paused)

    def test_learning_returns_to_the_same_customization_submenu(self):
        self.key(pygame.K_c)
        self.key(pygame.K_RETURN)
        self.app.menu_index = 2
        self.key(pygame.K_l)
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.custom_open)
        self.assertEqual(self.app.custom_page, "ghosts")
        self.assertEqual(self.app.menu_index, 2)

    def test_space_pauses_and_n_steps_the_animation(self):
        self.key(pygame.K_l)
        self.key(pygame.K_SPACE)
        for _ in range(20):
            self.app._tick()
        self.assertEqual(self.app.learning.frame, 0)
        self.key(scancode=pygame.KSCAN_N)
        self.assertEqual(self.app.learning.frame, 120)
        self.assertFalse(self.app.learning.playing)

    def test_r_replays_the_lesson_instead_of_restarting_the_game(self):
        game = self.app.game
        self.key(pygame.K_l)
        self.app.learning.elapsed = 200
        self.key(pygame.K_r)
        self.assertIs(self.app.game, game)
        self.assertEqual(self.app.learning.frame, 0)

    def test_keyboard_and_mouse_chapter_navigation(self):
        self.key(pygame.K_l)
        self.key(pygame.K_RIGHT)
        self.assertEqual(self.app.learning.index, 1)
        self.key(pygame.K_LEFT)
        self.assertEqual(self.app.learning.index, 0)
        self.click("learn:chapter:4")
        self.assertEqual(self.app.learning.index, 4)

    def test_mouse_speed_cycles_half_normal_and_double(self):
        self.key(pygame.K_l)
        self.click("learn:speed")
        self.assertEqual(self.app.learning.speed, 2)
        self.click("learn:speed")
        self.assertEqual(self.app.learning.speed, .5)
        self.click("learn:speed")
        self.assertEqual(self.app.learning.speed, 1)

    def test_details_scroll_by_wheel_and_keep_both_animation_buttons_clickable(self):
        self.key(pygame.K_l)
        self.click("learn:chapter:4")
        self.click("learn:detail")
        self.assertTrue(self.app.learning.details_open)
        self.app._event(pygame.event.Event(pygame.MOUSEWHEEL, y=-999, x=0))
        self.app._draw()
        self.assertEqual(self.app.learning.scroll_line, len(detail_lines(4)) - 11)
        self.click("learn:detail")
        self.assertFalse(self.app.learning.details_open)
        self.key(pygame.K_TAB)
        self.click("learn:animation")
        self.assertFalse(self.app.learning.details_open)

    def test_details_freeze_time_and_replay_returns_to_top(self):
        self.key(pygame.K_l)
        self.key(pygame.K_TAB)
        self.app.learning.scroll_line = 4
        for _ in range(20):
            self.app._tick()
        self.assertEqual(self.app.learning.frame, 0)
        self.key(pygame.K_r)
        self.assertEqual(self.app.learning.scroll_line, 0)

    def test_learning_does_not_enable_disabled_ghosts_in_the_real_game(self):
        self.app.customization.enabled_ghosts = frozenset()
        self.app.game.set_enabled_ghosts([])
        self.key(pygame.K_l)
        self.click("learn:chapter:4")
        self.assertTrue(any(a.kind == GhostKind.INKY for a in sample_lesson(4, 120).actors))
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.game.active_ghosts)
        self.assertFalse(self.app.customization.enabled_ghosts)

    def test_every_chapter_and_article_has_readable_bounded_controls(self):
        self.key(pygame.K_l)
        screen = pygame.Rect(0, 0, *SCREEN)
        for index, lesson in enumerate(LESSONS):
            self.app.learning.select(index)
            for details in (False, True):
                self.app.learning.details_open = details
                self.app._draw()
                self.assertEqual(len(self.app.renderer.buttons), 15)
                for rect in self.app.renderer.buttons.values():
                    self.assertTrue(screen.contains(rect))
            self.assertLessEqual(ui_image(lesson.title, WHITE, 13).get_width(), 208)
            self.assertTrue(all(ui_image(line, WHITE, 11).get_width() <= 184 for line in detail_lines(index)))


if __name__ == "__main__":
    unittest.main()
