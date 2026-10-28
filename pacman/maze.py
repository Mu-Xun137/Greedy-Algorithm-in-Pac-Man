"""Seeded, mirrored, braided mazes with a protected ghost house.

Generation uses a spanning tree on a coarse lattice, adds loops to every
leaf, then mirrors the result. The player's graph contains no dead ends:
the arcade ghosts never need an artificial escape U-turn in normal play.
"""

from collections import deque
from dataclasses import dataclass
import random

WIDTH = 28
HEIGHT = 31
TILE = 8
TUNNEL_ROW = 14
Tile = tuple[int, int]
DIRECTIONS: tuple[Tile, ...] = ((0, -1), (-1, 0), (0, 1), (1, 0))


def adjacent(tile: Tile, direction: int) -> Tile:
    dx, dy = DIRECTIONS[direction]
    return tile[0] + dx, tile[1] + dy


@dataclass
class Maze:
    seed: int
    floors: frozenset[Tile]
    pellets: frozenset[Tile]
    energizers: frozenset[Tile]
    no_up: frozenset[Tile]
    spawn: Tile = (13, 24)
    exit: Tile = (13, 11)
    fruit: Tile = (13, 17)

    @property
    def gates(self) -> frozenset[Tile]:
        return frozenset(((13, 12), (14, 12)))

    @property
    def house(self) -> frozenset[Tile]:
        return frozenset((x, y) for x in range(11, 17) for y in range(13, 16))

    def neighbor(self, tile: Tile, direction: int) -> Tile | None:
        x, y = adjacent(tile, direction)
        if y == TUNNEL_ROW:
            x %= WIDTH
        result = (x, y)
        return result if result in self.floors else None

    def exits(self, tile: Tile) -> list[int]:
        return [d for d in range(4) if self.neighbor(tile, d) is not None]

    def reachable(self, start: Tile | None = None) -> set[Tile]:
        found = {start or self.spawn}
        queue = deque(found)
        while queue:
            tile = queue.popleft()
            for direction in range(4):
                other = self.neighbor(tile, direction)
                if other is not None and other not in found:
                    found.add(other)
                    queue.append(other)
        return found

    def distances(self, target: Tile) -> dict[Tile, int]:
        """Only returning eyes / the demonstration player use graph distance."""
        distances = {target: 0}
        queue = deque([target])
        while queue:
            tile = queue.popleft()
            for direction in range(4):
                other = self.neighbor(tile, direction)
                if other is not None and other not in distances:
                    distances[other] = distances[tile] + 1
                    queue.append(other)
        return distances

    def validate(self) -> None:
        if self.reachable() != set(self.floors):
            raise ValueError("Maze is disconnected")
        if any(len(self.exits(tile)) < 2 for tile in self.floors):
            raise ValueError("Maze has a dead end")
        if any((WIDTH - 1 - x, y) not in self.floors for x, y in self.floors):
            raise ValueError("Maze lost its mirror symmetry")
        if len(self.energizers) != 4 or not self.energizers <= self.pellets:
            raise ValueError("Maze must have four reachable energizers")
        if self.house & self.floors or self.gates & self.floors:
            raise ValueError("Player can enter the ghost house")
        if not self.pellets <= self.floors:
            raise ValueError("Pellet inside a wall")
        if len(self.no_up) != 4 or any(
            not {0, 1, 3} <= set(self.exits(tile)) for tile in self.no_up
        ):
            raise ValueError("Invalid arcade no-up junction")


def generate(seed: int) -> Maze:
    rng = random.Random(seed)
    xs = (1, 4, 7, 10, 12)
    ys = (1, 4, 7, 10, 14, 18, 21, 24, 27, 29)

    def protected(tile: Tile) -> bool:
        x, y = tile
        return 10 <= x <= 17 and 12 <= y <= 16

    def segment(a: Tile, b: Tile) -> list[Tile]:
        ax, ay = a
        bx, by = b
        if ay == by:
            return [(x, ay) for x in range(min(ax, bx), max(ax, bx) + 1)]
        return [(ax, y) for y in range(min(ay, by), max(ay, by) + 1)]

    nodes = [(x, y) for x in xs for y in ys if not protected((x, y))]
    parent = {tile: tile for tile in nodes}

    def root(tile: Tile) -> Tile:
        while parent[tile] != tile:
            parent[tile] = parent[parent[tile]]
            tile = parent[tile]
        return tile

    edges: list[tuple[Tile, Tile, list[Tile]]] = []
    for ix, x in enumerate(xs):
        for iy, y in enumerate(ys):
            a = (x, y)
            if a not in parent:
                continue
            for b in ((xs[ix + 1], y) if ix + 1 < len(xs) else a,
                      (x, ys[iy + 1]) if iy + 1 < len(ys) else a):
                if b == a or b not in parent:
                    continue
                path = segment(a, b)
                if not any(protected(tile) for tile in path):
                    edges.append((a, b, path))
    rng.shuffle(edges)
    chosen: set[int] = set()
    degree = dict.fromkeys(nodes, 0)
    for i, (a, b, _) in enumerate(edges):
        if root(a) != root(b):
            parent[root(a)] = root(b)
            chosen.add(i)
            degree[a] += 1
            degree[b] += 1
    # Braid leaves rather than letting a ghost violate the no-reversal rule.
    for node in rng.sample(nodes, len(nodes)):
        if degree[node] < 2:
            choices = [i for i, (a, b, _) in enumerate(edges)
                       if i not in chosen and node in (a, b)]
            if choices:
                i = rng.choice(choices)
                a, b, _ = edges[i]
                chosen.add(i)
                degree[a] += 1
                degree[b] += 1
    for i, (a, b, _) in enumerate(edges):
        if i not in chosen and rng.random() < 0.08:
            chosen.add(i)

    floors = set(nodes)
    for i in chosen:
        floors.update(edges[i][2])
    # Long border passages are a characteristic of the 1980 arcade maze.
    for a, b in (((1, 1), (12, 1)), ((1, 29), (12, 29)), ((1, 1), (1, 29))):
        floors.update(segment(a, b))
    floors.update((WIDTH - 1 - x, y) for x, y in tuple(floors))
    for y in (1, 10, 18, 24, 29):
        floors.update(segment((12, y), (15, y)))
    for y in (4, 7, 21, 27):
        if rng.random() < 0.40:
            floors.update(segment((12, y), (15, y)))
    # The pen, exit porch, surrounding ring and side tunnel remain stable.
    for a, b in (
        ((9, 11), (18, 11)), ((9, 17), (18, 17)),
        ((9, 11), (9, 17)), ((18, 11), (18, 17)),
        ((0, 14), (9, 14)), ((18, 14), (27, 14)),
        ((10, 10), (10, 11)), ((17, 10), (17, 11)),
        ((12, 10), (12, 11)), ((15, 10), (15, 11)),
        ((10, 17), (10, 18)), ((17, 17), (17, 18)),
        ((12, 21), (12, 24)), ((15, 21), (15, 24)),
        ((10, 24), (17, 24)),
    ):
        floors.update(segment(a, b))

    # Symmetric quadrant energizers; choose an actual corridor, never a wall.
    power_top = min((t for t in floors if 1 <= t[0] <= 4 and 2 <= t[1] <= 7),
                    key=lambda t: (abs(t[0] - 1) + abs(t[1] - 4), t))
    power_bottom = min((t for t in floors if 1 <= t[0] <= 4 and 24 <= t[1] <= 28),
                       key=lambda t: (abs(t[0] - 1) + abs(t[1] - 27), t))
    energizers = frozenset((power_top, (27 - power_top[0], power_top[1]),
                            power_bottom, (27 - power_bottom[0], power_bottom[1])))
    empty = {(x, y) for x, y in floors if 9 <= x <= 18 and 10 <= y <= 18}
    empty.update((x, 14) for x in range(WIDTH))
    empty.update(((13, 24), (14, 24)))
    maze = Maze(seed, frozenset(floors), frozenset(floors - empty) | energizers,
                energizers, frozenset(((12, 11), (15, 11), (12, 24), (15, 24))))
    maze.validate()
    return maze
