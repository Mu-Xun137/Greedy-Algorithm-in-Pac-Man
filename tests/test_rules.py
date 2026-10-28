from pathlib import Path
import tempfile
import unittest

from pacman.maze import Maze, generate
from pacman.rules import (
    Direction as D, FrightRandom, GhostKind as K, Mode, ModeClock,
    SCATTER_TARGETS, choose_direction, elroy_stage, frightened_frames,
    frightened_flash, frame_steps, inky_target_points, personal_limit, schedule, target_tile, StepPattern,
)


def cross(no_up=False):
    floors = frozenset(((2, 2), (1, 2), (3, 2), (2, 1), (2, 3)))
    return Maze(0, floors, frozenset(), frozenset(),
                frozenset(((2, 2),)) if no_up else frozenset())


class TargetTests(unittest.TestCase):
    def target(self, kind, heading=D.RIGHT, tile=(20, 20), mode=Mode.CHASE, elroy=0):
        return target_tile(kind, tile, (10, 10), heading, (4, 4), mode, elroy)

    def test_blinky_uses_player_tile(self):
        self.assertEqual(self.target(K.BLINKY), (10, 10))

    def test_pinky_four_ahead_and_original_up_bug(self):
        for heading, expected in ((D.RIGHT, (14, 10)), (D.LEFT, (6, 10)),
                                   (D.DOWN, (10, 14)), (D.UP, (6, 6))):
            with self.subTest(heading=heading):
                self.assertEqual(self.target(K.PINKY, heading), expected)

    def test_inky_uses_blinky_vector_and_up_bug(self):
        self.assertEqual(self.target(K.INKY, D.RIGHT), (20, 16))
        self.assertEqual(self.target(K.INKY, D.UP), (12, 12))

    def test_inky_pivot_is_midpoint_between_blinky_and_target(self):
        for heading in D:
            pivot, target = inky_target_points((10, 10), heading, (4, 4))
            self.assertEqual((2 * pivot[0], 2 * pivot[1]), (target[0] + 4, target[1] + 4))
        self.assertEqual(inky_target_points((10, 10), D.UP, (4, 4)), ((8, 8), (12, 12)))

    def test_clyde_eight_tile_boundary(self):
        self.assertEqual(self.target(K.CLYDE, tile=(18, 10)), (10, 10))
        self.assertEqual(self.target(K.CLYDE, tile=(17, 10)), SCATTER_TARGETS[K.CLYDE])

    def test_scatter_targets_are_off_screen(self):
        for kind in K:
            self.assertEqual(self.target(kind, mode=Mode.SCATTER), SCATTER_TARGETS[kind])

    def test_elroy_targets_player_even_during_scatter(self):
        self.assertEqual(self.target(K.BLINKY, mode=Mode.SCATTER, elroy=1), (10, 10))
        self.assertEqual(self.target(K.PINKY, mode=Mode.SCATTER, elroy=1), SCATTER_TARGETS[K.PINKY])


class SteeringTests(unittest.TestCase):
    def test_ties_resolve_up_then_left_then_down_then_right(self):
        maze = cross()
        self.assertEqual(choose_direction(maze, (2, 2), D.UP, (1, 1)), D.UP)
        self.assertEqual(choose_direction(maze, (2, 2), D.LEFT, (1, 3)), D.LEFT)
        self.assertEqual(choose_direction(maze, (2, 2), D.RIGHT, (3, 3)), D.DOWN)

    def test_roaming_ghost_cannot_reverse_to_reach_target(self):
        direction = choose_direction(cross(), (2, 2), D.RIGHT, (1, 2))
        self.assertNotEqual(direction, D.LEFT)

    def test_red_junction_forbids_up_only_in_normal_modes(self):
        maze = cross(no_up=True)
        self.assertNotEqual(choose_direction(maze, (2, 2), D.RIGHT, (2, 0)), D.UP)
        self.assertEqual(choose_direction(maze, (2, 2), D.RIGHT, (2, 0), True, 3), D.UP)

    def test_frightened_rotation_uses_hardware_direction_order(self):
        # First try LEFT (2), which is reverse, then UP (3).
        self.assertEqual(choose_direction(cross(), (2, 2), D.RIGHT, (0, 0), True, 2), D.UP)

    def test_all_generated_junctions_have_a_legal_non_reverse_turn(self):
        for seed in range(30):
            maze = generate(seed)
            for tile in maze.floors:
                for heading in D:
                    if maze.neighbor(tile, heading.opposite) is None:
                        continue
                    chosen = choose_direction(maze, tile, heading, (13, 11))
                    self.assertIsNotNone(maze.neighbor(tile, chosen))
                    self.assertNotEqual(chosen, heading.opposite)


class TimingTests(unittest.TestCase):
    def test_first_scatter_lasts_exactly_420_ticks(self):
        clock = ModeClock(1)
        self.assertFalse(any(clock.tick() for _ in range(419)))
        self.assertEqual(clock.mode, Mode.SCATTER)
        self.assertTrue(clock.tick())
        self.assertEqual(clock.mode, Mode.CHASE)

    def test_frightened_pauses_the_mode_timer(self):
        clock = ModeClock(1)
        for _ in range(120):
            clock.tick()
        for _ in range(360):
            self.assertFalse(clock.tick(True))
        self.assertEqual(clock.elapsed, 120)
        self.assertEqual(clock.phase, 0)

    def test_all_level_schedules_and_one_tick_final_scatter(self):
        for level in (1, 2, 4, 5, 21, 256):
            clock = ModeClock(level)
            changes = []
            for duration in schedule(level)[:-1]:
                for _ in range(duration - 1):
                    self.assertFalse(clock.tick())
                changes.append(clock.tick())
            self.assertEqual(changes, [True] * 7)
            self.assertEqual(clock.mode, Mode.CHASE)
            self.assertFalse(clock.tick())
        self.assertEqual(schedule(2)[-2], 1)
        self.assertEqual(schedule(5)[5], 1037 * 60)

    def test_frightened_duration_drops_to_zero_on_17_and_19_plus(self):
        expected = (360, 300, 240, 180, 120, 300, 120, 120, 60, 300,
                    120, 60, 60, 180, 60, 60, 0, 60, 0, 0, 0)
        self.assertEqual(tuple(frightened_frames(i) for i in range(1, 22)), expected)

    def test_fright_flashes_every_14_ticks_at_the_end(self):
        self.assertFalse(frightened_flash(1, 200))
        self.assertTrue(frightened_flash(1, 28))
        self.assertFalse(frightened_flash(1, 42))
        self.assertFalse(frightened_flash(19, 0))

    def test_arcade_sixteen_frame_pixel_patterns(self):
        self.assertEqual("".join(str(frame_steps(1, StepPattern.GHOST, f)) for f in range(16)),
                         "0111111111111111")
        self.assertEqual("".join(str(frame_steps(1, StepPattern.GHOST_FRIGHT, f)) for f in range(16)),
                         "0110110101101101")
        self.assertEqual(sum(frame_steps(5, StepPattern.ELROY_TWO, f) for f in range(16)), 21)
        self.assertEqual(frame_steps(1, StepPattern.GHOST, 16), 0)

    def test_elroy_thresholds_and_post_death_clyde_wait(self):
        self.assertEqual(elroy_stage(1, 21, False), 0)
        self.assertEqual(elroy_stage(1, 20, False), 1)
        self.assertEqual(elroy_stage(1, 10, False), 2)
        self.assertEqual(elroy_stage(1, 1, True), 0)
        self.assertEqual(elroy_stage(12, 80, False), 1)

    def test_personal_release_limits(self):
        self.assertEqual([personal_limit(kind, 1) for kind in K], [0, 0, 30, 60])
        self.assertEqual([personal_limit(kind, 2) for kind in K], [0, 0, 0, 50])
        self.assertEqual([personal_limit(kind, 3) for kind in K], [0, 0, 0, 0])


class RandomTests(unittest.TestCase):
    def test_address_recurrence_and_low_bits(self):
        memory = bytes(i & 255 for i in range(8192))
        rng = FrightRandom(memory)
        for index in (1, 6, 31, 156, 781, 3906):
            self.assertEqual(rng.direction(), memory[index] & 3)
            self.assertEqual(rng.index, index)

    def test_default_stream_restarts_identically_every_life(self):
        rng = FrightRandom()
        first = [rng.direction() for _ in range(200)]
        rng.reset()
        self.assertEqual(first, [rng.direction() for _ in range(200)])

    def test_user_memory_file_and_two_rom_directory(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory)
            self.assertTrue(path.resolve().is_relative_to(root))
            memory = bytes(i & 255 for i in range(8192))
            (path / "dump.bin").write_bytes(memory)
            self.assertEqual(FrightRandom.from_path(path / "dump.bin").memory, memory)
            (path / "pacman.6e").write_bytes(memory[:4096])
            (path / "pacman.6f").write_bytes(memory[4096:])
            self.assertEqual(FrightRandom.from_path(path).memory, memory)
            (path / "pacman.6f").write_bytes(b"short")
            with self.assertRaises(ValueError):
                FrightRandom.from_path(path)

    def test_short_memory_is_rejected(self):
        with self.assertRaises(ValueError):
            FrightRandom(b"short")


if __name__ == "__main__":
    unittest.main()
