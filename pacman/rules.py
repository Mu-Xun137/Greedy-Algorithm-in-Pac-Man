"""Arcade ghost rules, isolated from rendering and map generation.

Coordinates use screen axes (+y down). Preference is UP, LEFT, DOWN, RIGHT.
Sources and the distinction from ROM emulation are documented in README.md.
"""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from .maze import DIRECTIONS, Maze, Tile, adjacent


class Direction(IntEnum):
    UP = 0
    LEFT = 1
    DOWN = 2
    RIGHT = 3

    @property
    def opposite(self) -> "Direction":
        return Direction((int(self) + 2) % 4)


class Mode(IntEnum):
    SCATTER = 0
    CHASE = 1


class GhostKind(IntEnum):
    BLINKY = 0
    PINKY = 1
    INKY = 2
    CLYDE = 3


class GhostState(IntEnum):
    ROAMING = 0
    HOUSE = 1
    LEAVING = 2
    EYES = 3
    ENTERING = 4
    EATEN = 5


class StepPattern(IntEnum):
    PLAYER = 0
    GHOST = 1
    PLAYER_FRIGHT = 2
    GHOST_FRIGHT = 3
    TUNNEL = 4
    ELROY_ONE = 5
    ELROY_TWO = 6


# Arcade 16-frame movement tables documented by Jamey Pittman. Each digit
# is a number of pixels, not a floating-point average speed. See sources.
STEP_TABLES = (
    ("1111111111111111", "0111111111111111", "1111211111112111",
     "0110110101101101", "0101010101010101", "1111111111111111", "1111111121111111"),
    ("1111211111112111", "1111111121111111", "1111211112111121",
     "0110110110110111", "0110101011010101", "1111211111112111", "1111211112111121"),
    ("1121112111211121", "1111211112111121", "1121112111211121",
     "0111011101110111", "0110110101101101", "1121112111211121", "1121121121121121"),
    ("1111211111112111", "1111211112111121", "0000000000000000",
     "0000000000000000", "0110110101101101", "1121112111211121", "1121121121121121"),
)


def frame_steps(level: int, pattern: StepPattern, frame: int) -> int:
    group = 0 if level == 1 else 1 if level <= 4 else 2 if level <= 20 else 3
    return int(STEP_TABLES[group][pattern][frame % 16])


SCATTER_TARGETS: tuple[Tile, ...] = ((25, -3), (2, -3), (27, 31), (0, 31))
FRIGHT_SECONDS = (6, 5, 4, 3, 2, 5, 2, 2, 1, 5, 2, 1, 1, 3, 1, 1, 0, 1)
FRIGHT_FLASHES = (5, 5, 5, 5, 5, 5, 5, 5, 3, 5, 5, 3, 3, 5, 3, 3, 0, 3)
ELROY_ONE = (20, 30, 40, 40, 40, 50, 50, 50, 60, 60, 60, 80, 80, 80,
             100, 100, 100, 100, 120, 120, 120)
ELROY_TWO = (10, 15, 20, 20, 20, 25, 25, 25, 30, 30, 30, 40, 40, 40,
             50, 50, 50, 50, 60, 60, 60)


def schedule(level: int) -> tuple[int | None, ...]:
    if level == 1:
        seconds = (7, 20, 7, 20, 5, 20, 5)
        return tuple(s * 60 for s in seconds) + (None,)
    first = 7 if level <= 4 else 5
    long_chase = 1033 if level <= 4 else 1037
    return (first * 60, 1200, first * 60, 1200, 300, long_chase * 60, 1, None)


@dataclass
class ModeClock:
    level: int
    phase: int = 0
    elapsed: int = 0

    @property
    def mode(self) -> Mode:
        return Mode(self.phase % 2)

    def tick(self, frightened: bool = False) -> bool:
        if frightened:
            return False
        duration = schedule(self.level)[self.phase]
        if duration is None:
            return False
        self.elapsed += 1
        if self.elapsed >= duration:
            self.phase += 1
            self.elapsed = 0
            return True
        return False


def squared_distance(a: Tile, b: Tile) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def inky_target_points(player: Tile, heading: Direction, blinky: Tile) -> tuple[Tile, Tile]:
    """Return the two-ahead pivot and its reflection of Blinky, including the up bug."""
    dx, dy = DIRECTIONS[heading]
    pivot = (player[0] + 2 * dx - (2 if heading == Direction.UP else 0),
             player[1] + 2 * dy)
    target = (2 * pivot[0] - blinky[0], 2 * pivot[1] - blinky[1])
    return pivot, target


def target_tile(kind: GhostKind, tile: Tile, player: Tile,
                heading: Direction, blinky: Tile, mode: Mode,
                elroy: int = 0) -> Tile:
    if mode == Mode.SCATTER and not (kind == GhostKind.BLINKY and elroy):
        return SCATTER_TARGETS[kind]
    dx, dy = DIRECTIONS[heading]
    if kind == GhostKind.BLINKY:
        return player
    if kind == GhostKind.PINKY:
        # The Z80 carry bug offsets both x and y when Pac-Man faces up.
        return player[0] + 4 * dx - (4 if heading == Direction.UP else 0), player[1] + 4 * dy
    if kind == GhostKind.INKY:
        return inky_target_points(player, heading, blinky)[1]
    return player if squared_distance(tile, player) >= 64 else SCATTER_TARGETS[kind]


def choose_direction(maze: Maze, tile: Tile, heading: Direction,
                     target: Tile, frightened: bool = False,
                     random_direction: int = 0) -> Direction:
    """One-tile Euclidean comparison, never global pursuit pathfinding."""
    exits = [Direction(d) for d in maze.exits(tile) if d != heading.opposite]
    if not frightened and tile in maze.no_up:
        exits = [d for d in exits if d != Direction.UP]
    if not exits:
        # The generator excludes this situation. It also makes custom test
        # maps and edited maps fail gracefully rather than freezing an actor.
        exits = [Direction(d) for d in maze.exits(tile)]
    if not exits:
        return heading
    if frightened:
        # Hardware encoding: RIGHT=0, DOWN=1, LEFT=2, UP=3. Incrementing
        # the code rotates clockwise until a legal, non-reversing exit.
        hardware = (Direction.RIGHT, Direction.DOWN, Direction.LEFT, Direction.UP)
        for offset in range(4):
            candidate = hardware[(random_direction + offset) & 3]
            if candidate in exits:
                return candidate
    # Compare raw adjacent coordinates, even at the wrap tunnel. A ghost
    # cannot reason about the globally shorter route through the tunnel.
    return min(exits, key=lambda d: (squared_distance(adjacent(tile, d), target), int(d)))


class FrightRandom:
    """The arcade address recurrence with an optional user-supplied ROM table.

    No commercial ROM bytes are bundled. The standalone table is generated
    deterministically; it preserves the selector but not the ROM sequence.
    """

    def __init__(self, memory: bytes | None = None):
        if memory is not None and len(memory) < 8192:
            raise ValueError("RNG memory must contain at least 8192 bytes")
        if memory is None:
            state = 0xC0FFEE
            table = bytearray()
            for _ in range(8192):
                state ^= (state << 13) & 0xFFFFFFFF
                state ^= state >> 17
                state ^= (state << 5) & 0xFFFFFFFF
                table.append((state >> 8) & 0xFF)
            memory = bytes(table)
        self.memory = memory[:8192]
        self.index = 0

    @classmethod
    def from_path(cls, path: Path) -> "FrightRandom":
        if path.is_dir():
            first = (path / "pacman.6e").read_bytes()
            second = (path / "pacman.6f").read_bytes()
            if len(first) != 4096 or len(second) != 4096:
                raise ValueError("pacman.6e and pacman.6f must each be 4096 bytes")
            return cls(first + second)
        return cls(path.read_bytes())

    def reset(self) -> None:
        self.index = 0

    def direction(self) -> int:
        self.index = (5 * self.index + 1) & 0x1FFF
        return self.memory[self.index] & 3


def frightened_frames(level: int) -> int:
    return FRIGHT_SECONDS[level - 1] * 60 if level <= 18 else 0


def frightened_flash(level: int, remaining: int) -> bool:
    flashes = FRIGHT_FLASHES[level - 1] if level <= 18 else 0
    interval = remaining // 14
    return interval <= flashes * 2 - 1 and interval % 2 == 0


def elroy_stage(level: int, remaining: int, wait_for_clyde: bool) -> int:
    if wait_for_clyde:
        return 0
    index = min(level, 21) - 1
    return 2 if remaining <= ELROY_TWO[index] else 1 if remaining <= ELROY_ONE[index] else 0


def personal_limit(kind: GhostKind, level: int) -> int:
    if kind == GhostKind.INKY:
        return 30 if level == 1 else 0
    if kind == GhostKind.CLYDE:
        return 60 if level == 1 else 50 if level == 2 else 0
    return 0


def fruit_value(level: int) -> int:
    return (100, 300, 500, 500, 700, 700, 1000, 1000,
            2000, 2000, 3000, 3000)[level - 1] if level <= 12 else 5000
