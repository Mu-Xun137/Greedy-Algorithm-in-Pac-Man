import unittest

from pacman.maze import HEIGHT, WIDTH, generate


class MazeTests(unittest.TestCase):
    def test_many_maps_obey_playability_invariants(self):
        for seed in range(1000):
            with self.subTest(seed=seed):
                maze = generate(seed)
                maze.validate()
                self.assertGreater(len(maze.pellets), 240)
                self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in maze.floors))

    def test_same_seed_reproduces_every_tile(self):
        self.assertEqual(generate(0xDEADBEEF), generate(0xDEADBEEF))

    def test_new_seeds_change_the_actual_geometry(self):
        geometries = {generate(seed).floors for seed in range(200)}
        self.assertEqual(len(geometries), 200)

    def test_tunnel_wraps_in_both_directions(self):
        maze = generate(42)
        self.assertEqual(maze.neighbor((0, 14), 1), (27, 14))
        self.assertEqual(maze.neighbor((27, 14), 3), (0, 14))
        self.assertIsNone(maze.neighbor((0, 13), 1))

    def test_house_is_inaccessible_to_the_player(self):
        maze = generate(42)
        self.assertIsNone(maze.neighbor((13, 11), 2))
        self.assertFalse(maze.house & maze.reachable())

    def test_one_energizer_in_each_quadrant(self):
        maze = generate(55)
        quadrants = {(x < WIDTH // 2, y < HEIGHT // 2) for x, y in maze.energizers}
        self.assertEqual(len(quadrants), 4)


if __name__ == "__main__":
    unittest.main()
