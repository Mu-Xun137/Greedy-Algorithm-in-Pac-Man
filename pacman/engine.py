"""Deterministic 60 Hz arcade simulation; standard library only."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .customization import ALL_GHOSTS, valid_ghosts
from .maze import DIRECTIONS, TILE, TUNNEL_ROW, WIDTH, Maze, Tile, generate
from .rules import (
    Direction, FrightRandom, GhostKind, GhostState, Mode, ModeClock, StepPattern, elroy_stage,
    frame_steps, frightened_frames, fruit_value, inky_target_points, personal_limit, target_tile,
    choose_direction,
)

FPS = 60


class Phase(Enum):
    READY = "READY!"
    PLAYING = "PLAYING"
    DYING = "DYING"
    CLEAR = "CLEAR"
    GAME_OVER = "GAME OVER"


@dataclass
class Actor:
    x: int
    y: int
    direction: Direction = Direction.LEFT
    moving: bool = False
    distance: int = 0
    frames: int = 0

    @property
    def tile(self) -> Tile:
        return self.x // TILE, self.y // TILE

    @property
    def centered(self) -> bool:
        return self.x % TILE == 4 and self.y % TILE == 4

@dataclass
class Ghost(Actor):
    kind: GhostKind = GhostKind.BLINKY
    state: GhostState = GhostState.HOUSE
    frightened: bool = False
    reverse_pending: bool = False
    plan: Direction | None = None
    plan_tile: Tile | None = None
    target: Tile = (0, 0)
    enabled: bool = True


class Game:
    def __init__(self, seed: int, rng: FrightRandom | None = None,
                 enabled_ghosts: Iterable[GhostKind] | None = None):
        self.seed = seed & 0xFFFFFFFF
        self.enabled_ghosts = valid_ghosts(ALL_GHOSTS if enabled_ghosts is None else enabled_ghosts)
        self.random = rng or FrightRandom()
        self.level = 1
        self.score = 0
        self.lives = 3
        self.extra_life = False
        self.ticks = 0
        self.events: list[str] = []
        self.personal_counts = [0, 0, 0, 0]
        self._new_level()

    def _new_level(self) -> None:
        level_seed = (self.seed + 0x9E3779B9 * (self.level - 1)) & 0xFFFFFFFF
        self.maze = generate(level_seed)
        self.pellets = set(self.maze.pellets)
        self.powers = set(self.maze.energizers)
        self.initial_pellets = len(self.pellets)
        self.eaten = 0
        self.personal_counts = [0, 0, 0, 0]
        self.fruit_ticks = 0
        self.fruit_spawns: set[int] = set()
        self.eyes_distances = self.maze.distances(self.maze.exit)
        self._reset_actors(False)

    def _reset_actors(self, after_death: bool) -> None:
        self.player = Actor(self.maze.spawn[0] * TILE + 4, self.maze.spawn[1] * TILE + 4)
        self.wanted = Direction.LEFT
        positions = ((13, 11), (13, 14), (11, 14), (16, 14))
        self.ghosts = [
            Ghost(x=x * TILE + 4, y=y * TILE + 4,
                  direction=Direction.LEFT if i == 0 else Direction.UP,
                  kind=GhostKind(i),
                  state=GhostState.ROAMING if i == 0 else GhostState.HOUSE,
                  enabled=GhostKind(i) in self.enabled_ghosts)
            for i, (x, y) in enumerate(positions)
        ]
        self.clock = ModeClock(self.level)
        self.fright_left = 0
        self.ghost_chain = 0
        self.eat_pause = 0
        self.freeze_ticks = 0
        self.popup: tuple[str, int, int] | None = None
        self.popup_ticks = 0
        self.global_counter = after_death and any(k != GhostKind.BLINKY for k in self.enabled_ghosts)
        self.global_dots = 0
        self.since_dot = 0
        self.wait_for_clyde = after_death and GhostKind.CLYDE in self.enabled_ghosts
        self.random.reset()
        self.phase = Phase.READY
        self.phase_ticks = 120 if after_death else 150
        self.events.append("ready")

    @property
    def elroy(self) -> int:
        if GhostKind.BLINKY not in self.enabled_ghosts:
            return 0
        return elroy_stage(self.level, len(self.pellets), self.wait_for_clyde)

    @property
    def active_ghosts(self) -> tuple[Ghost, ...]:
        return tuple(ghost for ghost in self.ghosts if ghost.enabled)

    def set_enabled_ghosts(self, kinds: Iterable[GhostKind]) -> None:
        """Apply a menu change without leaving invisible colliders behind."""
        enabled = valid_ghosts(kinds)
        seats = ((13, 11), (13, 14), (11, 14), (16, 14))
        for ghost in self.ghosts:
            if ghost.kind in enabled and not ghost.enabled:
                x, y = seats[ghost.kind]
                ghost.x, ghost.y = x * TILE + 4, y * TILE + 4
                ghost.direction = Direction.LEFT if ghost.kind == GhostKind.BLINKY else Direction.UP
                ghost.state = GhostState.ROAMING if ghost.kind == GhostKind.BLINKY else GhostState.HOUSE
                ghost.plan = ghost.plan_tile = None
                ghost.frames = 0
                ghost.frightened = bool(self.fright_left)
                ghost.reverse_pending = False
            ghost.enabled = ghost.kind in enabled
        self.enabled_ghosts = enabled
        if GhostKind.CLYDE not in enabled:
            self.wait_for_clyde = False

    def drain_events(self) -> list[str]:
        events, self.events = self.events, []
        return events

    def steer(self, direction: Direction) -> None:
        self.wanted = direction

    def _score(self, points: int) -> None:
        self.score += points
        if self.score >= 10000 and not self.extra_life:
            self.extra_life = True
            self.lives += 1
            self.events.append("extra")

    def _pixel(self, actor: Actor) -> None:
        dx, dy = DIRECTIONS[actor.direction]
        actor.x += dx
        actor.y += dy
        if actor.y // TILE == TUNNEL_ROW:
            actor.x %= WIDTH * TILE
        actor.distance += 1
        actor.moving = True

    def _player_tick(self) -> None:
        player = self.player
        player.moving = False
        pattern = StepPattern.PLAYER_FRIGHT if self.fright_left else StepPattern.PLAYER
        count = frame_steps(self.level, pattern, player.frames)
        player.frames += 1
        if self.eat_pause:
            self.eat_pause -= 1
            return
        for _ in range(count):
            # A reversal can happen between tile centers, just like the stick.
            if self.wanted == player.direction.opposite:
                player.direction = self.wanted
            if player.centered:
                if self.maze.neighbor(player.tile, self.wanted) is not None:
                    player.direction = self.wanted
                if self.maze.neighbor(player.tile, player.direction) is None:
                    break
            self._pixel(player)
            if self._consume():
                break

    def _consume(self) -> bool:
        tile = self.player.tile
        # Dots are consumed when the tile's center is crossed, not on entry.
        if tile in self.pellets and self.player.centered:
            self.pellets.remove(tile)
            self.eaten += 1
            self._dot_counter()
            if tile in self.powers:
                self.powers.remove(tile)
                self._score(50)
                self.eat_pause = 3
                self._energize()
                self.events.append("power")
            else:
                self._score(10)
                self.eat_pause = 1
                self.events.append("dot")
            for threshold in (70, 170):
                if self.eaten == threshold and threshold not in self.fruit_spawns:
                    self.fruit_spawns.add(threshold)
                    self.fruit_ticks = 570  # midpoint of the arcade's 9–10 s
            if not self.pellets:
                self.phase = Phase.CLEAR
                self.phase_ticks = 150
                self.fright_left = 0
                self.events.append("clear")
            return True
        return False

    def _dot_counter(self) -> None:
        self.since_dot = 0
        if self.global_counter:
            self.global_dots += 1
        else:
            for ghost in self.ghosts[1:]:
                if ghost.enabled and ghost.state == GhostState.HOUSE:
                    self.personal_counts[ghost.kind] += 1
                    break

    def _leave(self, ghost: Ghost) -> None:
        ghost.state = GhostState.LEAVING
        ghost.plan = None
        ghost.plan_tile = None
        if ghost.kind == GhostKind.CLYDE:
            self.wait_for_clyde = False

    def _release_tick(self) -> None:
        waiting = [g for g in self.ghosts[1:] if g.enabled and g.state == GhostState.HOUSE]
        if self.global_counter:
            for kind, threshold in ((GhostKind.PINKY, 7), (GhostKind.INKY, 17), (GhostKind.CLYDE, 32)):
                ghost = self.ghosts[kind]
                # Equality is deliberate: it retains the arcade house trap.
                if ghost.enabled and self.global_dots == threshold and ghost.state == GhostState.HOUSE:
                    last_kind = max(self.enabled_ghosts - {GhostKind.BLINKY}, default=GhostKind.BLINKY)
                    if kind == last_kind:
                        self.global_counter = False
                        self.global_dots = 0
                    self._leave(ghost)
                    return
        elif waiting:
            ghost = waiting[0]
            if self.personal_counts[ghost.kind] >= personal_limit(ghost.kind, self.level):
                self._leave(ghost)
                return
        self.since_dot += 1
        timeout = (4 if self.level < 5 else 3) * FPS
        if self.since_dot >= timeout:
            self.since_dot = 0
            if waiting:
                self._leave(waiting[0])

    def _energize(self) -> None:
        self.fright_left = frightened_frames(self.level)
        self.ghost_chain = 0
        for ghost in self.active_ghosts:
            if ghost.state not in (GhostState.EYES, GhostState.ENTERING, GhostState.EATEN):
                ghost.frightened = bool(self.fright_left)
                ghost.reverse_pending = True

    def _ghost_steps(self, ghost: Ghost) -> int:
        if ghost.state in (GhostState.EYES, GhostState.ENTERING):
            return 2
        if ghost.state == GhostState.EATEN:
            return 0
        if ghost.state in (GhostState.HOUSE, GhostState.LEAVING):
            return frame_steps(1, StepPattern.TUNNEL, ghost.frames)
        pattern = StepPattern.GHOST
        x, y = ghost.tile
        if y == TUNNEL_ROW and (x <= 5 or x >= WIDTH - 6):
            pattern = StepPattern.TUNNEL
        elif ghost.frightened:
            pattern = StepPattern.GHOST_FRIGHT
        elif ghost.kind == GhostKind.BLINKY and self.elroy:
            pattern = StepPattern.ELROY_ONE if self.elroy == 1 else StepPattern.ELROY_TWO
        return frame_steps(self.level, pattern, ghost.frames)

    def _ghost_target(self, ghost: Ghost) -> Tile:
        return target_tile(ghost.kind, ghost.tile, self.player.tile,
                           self.player.direction, self.ghosts[0].tile,
                           self.clock.mode, self.elroy if ghost.kind == GhostKind.BLINKY else 0)

    def visible_target(self, ghost: Ghost) -> Tile | None:
        """Current greedy formula, without changing a committed AI turn."""
        if not ghost.enabled or ghost.frightened or ghost.state != GhostState.ROAMING:
            return None
        return self._ghost_target(ghost)

    def inky_construction(self) -> tuple[Tile, Tile, Tile] | None:
        """Blinky reference -> two-ahead pivot -> Inky target, only while chasing."""
        inky = self.ghosts[GhostKind.INKY]
        if self.clock.mode != Mode.CHASE or self.visible_target(inky) is None:
            return None
        reference = self.ghosts[GhostKind.BLINKY].tile
        pivot, target = inky_target_points(self.player.tile, self.player.direction, reference)
        return reference, pivot, target

    def _house_pixel(self, ghost: Ghost) -> None:
        center_x = self.maze.exit[0] * TILE + 4
        exit_y = self.maze.exit[1] * TILE + 4
        home_y = 14 * TILE + 4
        if ghost.state == GhostState.HOUSE:
            if ghost.y <= 13 * TILE + 4:
                ghost.direction = Direction.DOWN
            elif ghost.y >= 15 * TILE + 4:
                ghost.direction = Direction.UP
        elif ghost.state == GhostState.ENTERING:
            seat_x = (13, 13, 11, 16)[ghost.kind] * TILE + 4
            if ghost.y < home_y:
                ghost.direction = Direction.DOWN
            elif ghost.x != seat_x:
                ghost.direction = Direction.RIGHT if ghost.x < seat_x else Direction.LEFT
            else:
                # Regenerated ghosts are immune to the current energizer.
                ghost.frightened = False
                ghost.reverse_pending = False
                if self.global_counter and ghost.kind != GhostKind.BLINKY:
                    ghost.state = GhostState.HOUSE
                else:
                    self._leave(ghost)
                return
        elif ghost.state == GhostState.LEAVING:
            if ghost.x != center_x:
                ghost.direction = Direction.RIGHT if ghost.x < center_x else Direction.LEFT
            elif ghost.y > exit_y:
                ghost.direction = Direction.UP
            else:
                ghost.state = GhostState.ROAMING
                ghost.direction = Direction.RIGHT if ghost.reverse_pending else Direction.LEFT
                ghost.reverse_pending = False
                self._plan(ghost)
                self._pixel(ghost)
                return
        self._pixel(ghost)

    def _plan(self, ghost: Ghost) -> None:
        next_tile = self.maze.neighbor(ghost.tile, ghost.direction)
        if next_tile is None:
            ghost.plan = None
            ghost.plan_tile = None
            return
        ghost.target = self._ghost_target(ghost)
        ghost.plan = choose_direction(self.maze, next_tile, ghost.direction, ghost.target,
                                      ghost.frightened,
                                      self.random.direction() if ghost.frightened else 0)
        ghost.plan_tile = next_tile

    def _ghost_pixel(self, ghost: Ghost) -> None:
        if ghost.state in (GhostState.HOUSE, GhostState.LEAVING, GhostState.ENTERING):
            self._house_pixel(ghost)
            return
        if ghost.state == GhostState.EYES:
            if ghost.centered:
                if ghost.tile == self.maze.exit:
                    ghost.state = GhostState.ENTERING
                    ghost.direction = Direction.DOWN
                    self._house_pixel(ghost)
                    return
                # The arcade's fixed-house return routes cannot serve an
                # arbitrary maze. A distance field guarantees eyes get home.
                ghost.direction = min(
                    (Direction(d) for d in self.maze.exits(ghost.tile)),
                    key=lambda d: (self.eyes_distances[self.maze.neighbor(ghost.tile, d)], int(d)))
            self._pixel(ghost)
            return
        if ghost.centered:
            if ghost.plan is not None and ghost.plan_tile == ghost.tile:
                ghost.direction = ghost.plan
            elif self.maze.neighbor(ghost.tile, ghost.direction) is None:
                ghost.direction = choose_direction(self.maze, ghost.tile, ghost.direction,
                                                    self._ghost_target(ghost), ghost.frightened,
                                                    self.random.direction() if ghost.frightened else 0)
            self._plan(ghost)
        before = ghost.tile
        self._pixel(ghost)
        if ghost.tile != before and ghost.reverse_pending:
            ghost.direction = ghost.direction.opposite
            ghost.reverse_pending = False
            ghost.plan = None
            ghost.plan_tile = None

    def _ghost_tick(self, ghost: Ghost) -> None:
        if not ghost.enabled:
            return
        ghost.moving = False
        count = self._ghost_steps(ghost)
        ghost.frames += 1
        for _ in range(count):
            self._ghost_pixel(ghost)

    def _collisions(self) -> None:
        for ghost in self.active_ghosts:
            if ghost.state not in (GhostState.ROAMING, GhostState.LEAVING):
                continue
            if ghost.tile != self.player.tile:
                continue
            if ghost.frightened:
                self.ghost_chain += 1
                points = 100 * (2 ** self.ghost_chain)
                self._score(points)
                self.popup = (str(points), ghost.x, ghost.y)
                self.popup_ticks = 60
                self.freeze_ticks = 60
                ghost.state = GhostState.EATEN
                ghost.frightened = False
                ghost.reverse_pending = False
                ghost.plan = None
                ghost.plan_tile = None
                self.events.append("ghost")
            else:
                self.phase = Phase.DYING
                self.phase_ticks = 110
                self.events.append("death")
                return

    def tick(self) -> None:
        self.ticks += 1
        if self.popup_ticks:
            self.popup_ticks -= 1
            if not self.popup_ticks:
                self.popup = None
        if self.phase == Phase.GAME_OVER:
            return
        if self.phase != Phase.PLAYING:
            self.phase_ticks -= 1
            if self.phase_ticks > 0:
                return
            if self.phase == Phase.READY:
                self.phase = Phase.PLAYING
            elif self.phase == Phase.CLEAR:
                self.level += 1
                self._new_level()
            elif self.phase == Phase.DYING:
                self.lives -= 1
                self.fruit_ticks = 0
                if self.lives <= 0:
                    self.phase = Phase.GAME_OVER
                else:
                    self._reset_actors(True)
            return
        if self.freeze_ticks:
            self.freeze_ticks -= 1
            for ghost in self.active_ghosts:
                if ghost.state in (GhostState.EYES, GhostState.ENTERING):
                    self._ghost_tick(ghost)
            if not self.freeze_ticks:
                for ghost in self.active_ghosts:
                    if ghost.state == GhostState.EATEN:
                        ghost.state = GhostState.EYES
            return
        if self.clock.tick(bool(self.fright_left)):
            for ghost in self.active_ghosts:
                if ghost.state not in (GhostState.EYES, GhostState.ENTERING):
                    ghost.reverse_pending = True
        if self.fright_left:
            self.fright_left -= 1
            if not self.fright_left:
                for ghost in self.active_ghosts:
                    ghost.frightened = False
        if self.fruit_ticks:
            self.fruit_ticks -= 1
        self._release_tick()
        self._player_tick()
        if self.phase != Phase.PLAYING:
            return
        for ghost in self.active_ghosts:
            self._ghost_tick(ghost)
        # One tile comparison per tick deliberately preserves pass-through
        # when both actors exchange neighboring tiles on the same frame.
        self._collisions()
        if self.fruit_ticks and self.player.tile == self.maze.fruit:
            points = fruit_value(self.level)
            self.fruit_ticks = 0
            self._score(points)
            self.popup = (str(points), self.player.x, self.player.y)
            self.popup_ticks = 100
            self.events.append("fruit")

    def demo_steer(self) -> None:
        """A demonstration joystick, independent of ghost steering rules."""
        if not self.player.centered or self.phase != Phase.PLAYING:
            return
        start = self.player.tile
        danger = {g.tile for g in self.active_ghosts
                  if g.state == GhostState.ROAMING and not g.frightened}
        blocked = set(danger)
        for tile in danger:
            blocked.update(self.maze.neighbor(tile, d) for d in range(4))
        queue = deque([(start, None)])
        seen = {start}
        while queue:
            tile, first = queue.popleft()
            if tile in self.pellets and first is not None:
                self.wanted = first
                return
            for d in range(4):
                other = self.maze.neighbor(tile, d)
                if other is not None and other not in seen and other not in blocked:
                    seen.add(other)
                    queue.append((other, Direction(d) if first is None else first))
        # If surrounded, head for the neighboring tile furthest from danger.
        options = self.maze.exits(start)
        if options:
            self.wanted = Direction(max(options, key=lambda d: min(
                (abs(self.maze.neighbor(start, d)[0] - t[0]) +
                 abs(self.maze.neighbor(start, d)[1] - t[1]) for t in danger), default=99)))
