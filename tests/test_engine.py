import random
import unittest

from pacman.engine import Game, Phase
from pacman.rules import Direction as D, GhostKind as K, GhostState as S, Mode


class GameplayTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(42)
        self.game.phase = Phase.PLAYING

    def test_personal_dot_counts_only_apply_to_first_waiting_ghost(self):
        game = self.game
        game._release_tick()
        self.assertEqual(game.ghosts[K.PINKY].state, S.LEAVING)
        for _ in range(29):
            game._dot_counter()
            game._release_tick()
        self.assertEqual(game.ghosts[K.INKY].state, S.HOUSE)
        self.assertEqual(game.personal_counts[K.CLYDE], 0)
        game._dot_counter()
        game._release_tick()
        self.assertEqual(game.ghosts[K.INKY].state, S.LEAVING)
        for _ in range(60):
            game._dot_counter()
            game._release_tick()
        self.assertEqual(game.ghosts[K.CLYDE].state, S.LEAVING)

    def test_idle_timeout_releases_ghost_without_eating(self):
        game = self.game
        game._release_tick()  # Pinky leaves immediately.
        for _ in range(239):
            game._release_tick()
        self.assertEqual(game.ghosts[K.INKY].state, S.HOUSE)
        game._release_tick()
        self.assertEqual(game.ghosts[K.INKY].state, S.LEAVING)

    def test_after_death_global_thresholds_are_7_17_32(self):
        game = self.game
        game.personal_counts[K.INKY] = 13
        game._reset_actors(True)
        self.assertEqual(game.personal_counts[K.INKY], 13)
        for dots in range(1, 33):
            game._dot_counter()
            game._release_tick()
            for kind, threshold in ((K.PINKY, 7), (K.INKY, 17), (K.CLYDE, 32)):
                self.assertEqual(game.ghosts[kind].state, S.LEAVING if dots >= threshold else S.HOUSE)
        self.assertFalse(game.global_counter)
        self.assertFalse(game.wait_for_clyde)

    def test_original_global_house_counter_trap_is_preserved(self):
        game = self.game
        game._reset_actors(True)
        game._leave(game.ghosts[K.CLYDE])  # Timer forces Clyde out early.
        for _ in range(33):
            game._dot_counter()
            game._release_tick()
        self.assertTrue(game.global_counter)
        game.ghosts[K.PINKY].state = S.HOUSE
        game._release_tick()
        self.assertEqual(game.ghosts[K.PINKY].state, S.HOUSE)

    def test_blinky_never_gets_trapped_in_house_after_being_eaten(self):
        game = self.game
        game._reset_actors(True)
        ghost = game.ghosts[K.BLINKY]
        ghost.state = S.ENTERING
        ghost.x, ghost.y = 108, 116
        game._house_pixel(ghost)
        self.assertEqual(ghost.state, S.LEAVING)

    def test_energizer_reverses_even_when_fright_duration_is_zero(self):
        game = self.game
        game.level = 19
        game._energize()
        self.assertEqual(game.fright_left, 0)
        self.assertTrue(all(g.reverse_pending for g in game.ghosts))
        self.assertFalse(any(g.frightened for g in game.ghosts))

    def test_frightened_expiration_does_not_signal_a_reversal(self):
        game = self.game
        game.fright_left = 1
        for ghost in game.ghosts:
            ghost.frightened = True
            ghost.reverse_pending = False
        game.tick()
        self.assertFalse(game.ghosts[K.BLINKY].frightened)
        self.assertFalse(game.ghosts[K.BLINKY].reverse_pending)

    def test_mode_reversal_waits_until_a_ghost_enters_next_tile(self):
        game = self.game
        ghost = game.ghosts[K.BLINKY]
        ghost.x, ghost.y = 4 * 8 + 4, 1 * 8 + 4
        ghost.direction = D.RIGHT
        ghost.reverse_pending = True
        for _ in range(3):
            game._ghost_pixel(ghost)
            self.assertEqual(ghost.direction, D.RIGHT)
        game._ghost_pixel(ghost)
        self.assertEqual(ghost.direction, D.LEFT)
        self.assertFalse(ghost.reverse_pending)

    def test_one_tile_lookahead_is_committed_before_the_intersection(self):
        game = self.game
        ghost = game.ghosts[K.BLINKY]
        ghost.x, ghost.y = 36, 12
        ghost.direction = D.RIGHT
        game.clock.phase = 1
        game.player.x, game.player.y = 44, 36
        game._ghost_pixel(ghost)
        planned = ghost.plan
        destination = ghost.plan_tile
        # Moving the target cannot change an already committed next turn.
        game.player.x, game.player.y = 12, 12
        while not ghost.centered:
            game._ghost_pixel(ghost)
        self.assertEqual(ghost.tile, destination)
        game._ghost_pixel(ghost)
        self.assertEqual(ghost.direction, planned)

    def test_ghost_combo_scores_200_400_800_1600(self):
        game = self.game
        for ghost in game.ghosts:
            ghost.x, ghost.y = game.player.x, game.player.y
            ghost.state = S.ROAMING
            ghost.frightened = True
        game._collisions()
        self.assertEqual(game.score, 3000)
        self.assertTrue(all(g.state == S.EATEN for g in game.ghosts))

    def test_regenerated_ghost_is_immune_to_current_power_pellet(self):
        game = self.game
        ghost = game.ghosts[K.PINKY]
        game.fright_left = 100
        ghost.state = S.ENTERING
        ghost.x, ghost.y = 108, 116
        ghost.frightened = True
        game._house_pixel(ghost)
        self.assertFalse(ghost.frightened)
        self.assertEqual(ghost.state, S.LEAVING)

    def test_eaten_ghost_waits_for_points_before_returning_home(self):
        game = self.game
        ghost = game.ghosts[K.BLINKY]
        ghost.x, ghost.y = game.player.x, game.player.y
        ghost.frightened = True
        game._collisions()
        previous = (ghost.x, ghost.y)
        for _ in range(59):
            game.tick()
        self.assertEqual(ghost.state, S.EATEN)
        self.assertEqual((ghost.x, ghost.y), previous)
        game.tick()
        self.assertEqual(ghost.state, S.EYES)

    def test_tile_swap_pass_through_and_same_tile_collision(self):
        game = self.game
        ghost = game.ghosts[K.BLINKY]
        ghost.x, ghost.y = game.player.x - 8, game.player.y
        game._collisions()
        self.assertEqual(game.phase, Phase.PLAYING)
        ghost.x = game.player.x
        game._collisions()
        self.assertEqual(game.phase, Phase.DYING)

    def test_one_extra_life_at_10000_only(self):
        self.game._score(10000)
        self.assertEqual(self.game.lives, 4)
        self.game._score(10000)
        self.assertEqual(self.game.lives, 4)

    def test_death_keeps_map_and_eaten_dots(self):
        game = self.game
        floors = game.maze.floors
        game.pellets.pop()
        remaining = set(game.pellets)
        game.phase = Phase.DYING
        game.phase_ticks = 1
        game.tick()
        self.assertEqual(game.lives, 2)
        self.assertEqual(game.phase, Phase.READY)
        self.assertEqual(game.maze.floors, floors)
        self.assertEqual(game.pellets, remaining)

    def test_clearing_board_generates_new_map_and_keeps_score(self):
        game = self.game
        old_maze = game.maze.floors
        game.pellets = {game.player.tile}
        game.score = 500
        game._consume()
        self.assertEqual(game.phase, Phase.CLEAR)
        for _ in range(150):
            game.tick()
        self.assertEqual(game.level, 2)
        self.assertEqual(game.phase, Phase.READY)
        self.assertNotEqual(game.maze.floors, old_maze)
        self.assertEqual(game.score, 510)

    def test_reverse_input_works_between_tile_centers(self):
        game = self.game
        game.player.x += 2
        game.player.direction = D.LEFT
        game.steer(D.RIGHT)
        previous = game.player.x
        game._player_tick()
        self.assertEqual(game.player.x, previous + 1)

    def test_fruit_appears_at_70_dots(self):
        game = self.game
        tile = game.player.tile
        game.pellets.add(tile)
        game.eaten = 69
        game._consume()
        self.assertEqual(game.fruit_ticks, 570)
        self.assertIn(70, game.fruit_spawns)

    def test_returning_eyes_reach_house_on_many_random_maps(self):
        for seed in range(20):
            game = Game(seed)
            starts = random.Random(seed).sample(sorted(game.maze.floors), 5)
            for start in starts:
                ghost = game.ghosts[K.INKY]
                ghost.state = S.EYES
                ghost.x, ghost.y = start[0] * 8 + 4, start[1] * 8 + 4
                for _ in range(2000):
                    game._ghost_tick(ghost)
                    if ghost.state == S.LEAVING:
                        break
                self.assertEqual(ghost.state, S.LEAVING, (seed, start))

    def test_roaming_ghosts_never_enter_walls_on_random_maps(self):
        for seed in range(12):
            game = Game(seed)
            for ghost in game.ghosts:
                ghost.x, ghost.y = 12, 12
                ghost.direction = D.RIGHT
                ghost.state = S.ROAMING
            for tick in range(1500):
                if tick % 300 == 0:
                    game._energize()
                for ghost in game.ghosts:
                    game._ghost_tick(ghost)
                    self.assertIn(ghost.tile, game.maze.floors, (seed, tick, ghost))

    def test_long_games_are_deterministic(self):
        def play():
            game = Game(90210)
            for _ in range(6000):
                game.demo_steer()
                game.tick()
                game.drain_events()
            return (game.score, game.lives, game.phase, game.player.tile,
                    [(g.tile, g.direction, g.state) for g in game.ghosts], game.random.index)
        first = play()
        self.assertGreater(first[0], 0)
        self.assertEqual(first, play())


if __name__ == "__main__":
    unittest.main()
