import json
from pathlib import Path
import tempfile
import unittest

from pacman.customization import Customization, read_customization, save_customization
from pacman.engine import Game, Phase
from pacman.rules import GhostKind as K, GhostState as S


class CustomizationTests(unittest.TestCase):
    def test_removing_inky_does_not_remove_blinky(self):
        settings = Customization()
        self.assertIsNone(settings.set_ghost(K.INKY, False))
        self.assertIn(K.BLINKY, settings.enabled_ghosts)
        self.assertNotIn(K.INKY, settings.enabled_ghosts)

    def test_removing_blinky_removes_inky_and_explains_dependency(self):
        settings = Customization()
        notice = settings.set_ghost(K.BLINKY, False)
        self.assertNotIn(K.BLINKY, settings.enabled_ghosts)
        self.assertNotIn(K.INKY, settings.enabled_ghosts)
        self.assertEqual(settings.enabled_ghosts, {K.PINKY, K.CLYDE})
        self.assertIn("同时关闭蓝鬼", notice)

    def test_enabling_inky_restores_required_blinky_with_a_notice(self):
        settings = Customization(enabled_ghosts=frozenset())
        notice = settings.set_ghost(K.INKY, True)
        self.assertEqual(settings.enabled_ghosts, {K.BLINKY, K.INKY})
        self.assertIn("同时开启红鬼", notice)

    def test_disabling_unrelated_ghost_never_removes_other_ghosts(self):
        for kind in (K.PINKY, K.CLYDE):
            settings = Customization()
            self.assertIsNone(settings.set_ghost(kind, False))
            self.assertEqual(settings.enabled_ghosts, set(K) - {kind})

    def test_all_preferences_round_trip_including_an_empty_ghost_set(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory).resolve() / "settings.json"
            self.assertTrue(path.is_relative_to(root))
            settings = Customization(frozenset(), True, False, "a" * 64)
            save_customization(settings, path)
            self.assertEqual(read_customization(path), settings)
            self.assertFalse(path.with_suffix(".tmp").exists())
            path.write_text(json.dumps({"ghosts": [False, True, True, True]}), encoding="utf-8")
            self.assertEqual(read_customization(path).enabled_ghosts, {K.PINKY, K.CLYDE})
            for bad in ("bad json", "[]", '{"ghosts": [1, 2, 3, 4]}'):
                path.write_text(bad, encoding="utf-8")
                self.assertEqual(read_customization(path).enabled_ghosts, set(K))


class DisabledGhostTests(unittest.TestCase):
    def test_game_also_enforces_dependency_if_menu_is_bypassed(self):
        game = Game(42, enabled_ghosts={K.INKY, K.CLYDE})
        self.assertEqual({g.kind for g in game.active_ghosts}, {K.CLYDE})

    def test_all_valid_combinations_survive_play_and_life_reset(self):
        checked = set()
        for mask in range(16):
            selected = {kind for kind in K if mask & (1 << kind)}
            game = Game(42, enabled_ghosts=selected)
            expected = Customization(frozenset(selected)).enabled_ghosts
            if expected in checked:
                continue
            checked.add(expected)
            for _ in range(1000):
                game.demo_steer()
                game.tick()
            self.assertEqual({g.kind for g in game.active_ghosts}, expected)
            game._reset_actors(True)
            self.assertEqual({g.kind for g in game.active_ghosts}, expected)
        self.assertEqual(len(checked), 12)

    def test_removed_ghosts_are_not_invisible_colliders_and_never_move(self):
        game = Game(42, enabled_ghosts=[])
        game.phase = Phase.PLAYING
        for ghost in game.ghosts:
            ghost.x, ghost.y = game.player.x, game.player.y
            ghost.state = S.ROAMING
        before = [(g.x, g.y, g.frames) for g in game.ghosts]
        game._collisions()
        for ghost in game.ghosts:
            game._ghost_tick(ghost)
        self.assertEqual(game.phase, Phase.PLAYING)
        self.assertEqual([(g.x, g.y, g.frames) for g in game.ghosts], before)

    def test_removing_pinky_does_not_block_inkys_dot_counter(self):
        game = Game(42, enabled_ghosts={K.BLINKY, K.INKY})
        for _ in range(30):
            game._dot_counter()
            game._release_tick()
        self.assertEqual(game.ghosts[K.INKY].state, S.LEAVING)
        self.assertEqual(game.personal_counts[K.PINKY], 0)

    def test_disabled_clyde_cannot_block_elroy_after_death(self):
        game = Game(42, enabled_ghosts={K.BLINKY})
        game.pellets = set(sorted(game.pellets)[:10])
        game._reset_actors(True)
        self.assertFalse(game.wait_for_clyde)
        self.assertEqual(game.elroy, 2)

    def test_disabled_final_ghost_cannot_keep_global_counter_active(self):
        game = Game(42, enabled_ghosts={K.BLINKY, K.PINKY})
        game._reset_actors(True)
        for _ in range(7):
            game._dot_counter()
            game._release_tick()
        self.assertEqual(game.ghosts[K.PINKY].state, S.LEAVING)
        self.assertFalse(game.global_counter)

    def test_live_disabling_and_reenabling_restores_ghost_at_its_spawn(self):
        game = Game(42)
        game.ghosts[K.BLINKY].x = 12
        game.set_enabled_ghosts({K.PINKY})
        self.assertEqual({g.kind for g in game.active_ghosts}, {K.PINKY})
        game.set_enabled_ghosts({K.BLINKY, K.PINKY})
        blinky = game.ghosts[K.BLINKY]
        self.assertEqual(blinky.tile, game.maze.exit)
        self.assertEqual(blinky.state, S.ROAMING)


if __name__ == "__main__":
    unittest.main()
