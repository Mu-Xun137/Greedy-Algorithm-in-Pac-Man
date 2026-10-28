import unittest

from pacman.learning import LESSONS, LOOP_FRAMES, LearningPlayer, sample_lesson
from pacman.rules import Direction as D, GhostKind as K, SCATTER_TARGETS


class LearningPlayerTests(unittest.TestCase):
    def test_play_pause_speed_step_and_loop(self):
        player = LearningPlayer(index=2)
        player.tick()
        self.assertEqual(player.frame, 1)
        player.playing = False
        player.tick()
        self.assertEqual(player.frame, 1)
        player.step()
        self.assertEqual(player.frame, 31)
        self.assertFalse(player.playing)
        player.replay()
        self.assertTrue(player.playing)
        self.assertEqual(player.frame, 0)
        player.change_speed()
        player.tick()
        self.assertEqual(player.frame, 2)
        player.elapsed = LOOP_FRAMES - 1
        player.tick()
        self.assertEqual(player.frame, 1)

    def test_half_speed_preserves_fractional_frames(self):
        player = LearningPlayer(speed_index=0)
        player.tick()
        self.assertEqual(player.elapsed, .5)
        self.assertEqual(player.frame, 0)
        player.tick()
        self.assertEqual(player.frame, 1)

    def test_reading_details_freezes_animation(self):
        player = LearningPlayer(details_open=True)
        for _ in range(100):
            player.tick()
        self.assertEqual(player.frame, 0)

    def test_chapter_selection_wraps_and_resets_the_reader(self):
        player = LearningPlayer(elapsed=200, scroll_line=20)
        player.select(-1)
        self.assertEqual(player.index, len(LESSONS) - 1)
        self.assertEqual(player.frame, 0)
        self.assertEqual(player.scroll_line, 0)
        player.select(len(LESSONS))
        self.assertEqual(player.index, 0)


class LessonAccuracyTests(unittest.TestCase):
    def test_greedy_intro_uses_the_explained_scores(self):
        frame = sample_lesson(0, 180)
        values = {c.direction: c.distance for c in frame.candidates}
        self.assertEqual((values[D.UP], values[D.LEFT], values[D.RIGHT]), (58, 80, 52))
        self.assertEqual(frame.choice, D.RIGHT)
        self.assertEqual(next(c for c in frame.candidates if c.direction == D.DOWN).blocked, "回头")

    def test_rule_animation_covers_ties_walls_no_up_and_no_reversal(self):
        expected = (D.UP, D.RIGHT, D.LEFT, D.LEFT)
        for case, direction in enumerate(expected):
            self.assertEqual(sample_lesson(1, 120 * case).choice, direction)
        self.assertEqual(sample_lesson(1, 120).candidates[D.UP].blocked, "墙")
        self.assertEqual(sample_lesson(1, 240).candidates[D.UP].blocked, "禁上")

    def test_red_target_always_matches_the_current_player_tile(self):
        for tick in range(0, LOOP_FRAMES, 7):
            frame = sample_lesson(2, tick)
            player = next(a for a in frame.actors if a.kind is None)
            self.assertEqual(frame.target, player.tile)

    def test_pinky_animation_preserves_the_upward_offset_bug(self):
        frame = sample_lesson(3, 180)
        player = next(a for a in frame.actors if a.kind is None)
        self.assertEqual(player.heading, D.UP)
        self.assertEqual(frame.target, (player.tile[0] - 4, player.tile[1] - 4))
        self.assertEqual(frame.ideal, (player.tile[0], player.tile[1] - 4))

    def test_inky_animation_uses_blinky_and_keeps_q_as_midpoint(self):
        for tick in range(0, LOOP_FRAMES, 7):
            frame = sample_lesson(4, tick)
            self.assertEqual((2 * frame.pivot[0], 2 * frame.pivot[1]),
                             (frame.reference[0] + frame.target[0], frame.reference[1] + frame.target[1]))
        a, b = sample_lesson(4, 30), sample_lesson(4, 150)
        self.assertEqual(a.pivot, b.pivot)
        self.assertEqual(b.target[0] - a.target[0], a.reference[0] - b.reference[0])

    def test_clyde_switches_on_the_exact_eight_tile_boundary(self):
        frame = sample_lesson(5, 30)
        player = next(a for a in frame.actors if a.kind is None)
        ghost = next(a for a in frame.actors if a.kind == K.CLYDE)
        self.assertEqual(ghost.tile, (4, 5))
        self.assertEqual(frame.target, player.tile)
        near = sample_lesson(5, 60)
        self.assertEqual(near.target, SCATTER_TARGETS[K.CLYDE])

    def test_frightened_lesson_does_not_invent_a_greedy_target(self):
        frame = sample_lesson(6, 360)
        self.assertEqual(frame.mode, "FRIGHTENED")
        self.assertIsNone(frame.target)
        self.assertTrue(next(a for a in frame.actors if a.kind == K.BLINKY).frightened)
        self.assertEqual(sample_lesson(6, 0).mode, "SCATTER")
        self.assertEqual(sample_lesson(6, 180).mode, "CHASE")

    def test_all_choreographed_ghosts_stay_on_the_teaching_board(self):
        for index in range(2, 7):
            for tick in range(LOOP_FRAMES):
                for actor in sample_lesson(index, tick).actors:
                    self.assertIn(actor.tile, sample_lesson(index, tick).maze.floors)


if __name__ == "__main__":
    unittest.main()
