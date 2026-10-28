"""Window, keyboard, fixed-step loop and local high-score persistence."""

import json
import hashlib
from pathlib import Path
import secrets

import pygame

from .audio import Audio
from .customization import Customization, read_customization, save_customization
from .engine import FPS, Game, Phase
from .learning import LearningPlayer
from .rules import Direction, FrightRandom, GhostKind, GhostState
from .video import BLACK, Renderer, SCREEN

KEYS = {
    pygame.K_UP: Direction.UP, pygame.K_w: Direction.UP,
    pygame.K_LEFT: Direction.LEFT, pygame.K_a: Direction.LEFT,
    pygame.K_DOWN: Direction.DOWN, pygame.K_s: Direction.DOWN,
    pygame.K_RIGHT: Direction.RIGHT, pygame.K_d: Direction.RIGHT,
}
SCAN_TO_KEY = {
    pygame.KSCAN_UP: pygame.K_UP, pygame.KSCAN_DOWN: pygame.K_DOWN,
    pygame.KSCAN_LEFT: pygame.K_LEFT, pygame.KSCAN_RIGHT: pygame.K_RIGHT,
    pygame.KSCAN_W: pygame.K_w, pygame.KSCAN_A: pygame.K_a,
    pygame.KSCAN_S: pygame.K_s, pygame.KSCAN_D: pygame.K_d,
    pygame.KSCAN_P: pygame.K_p, pygame.KSCAN_C: pygame.K_c,
    pygame.KSCAN_R: pygame.K_r, pygame.KSCAN_M: pygame.K_m,
    pygame.KSCAN_Q: pygame.K_q, pygame.KSCAN_H: pygame.K_h,
    pygame.KSCAN_L: pygame.K_l, pygame.KSCAN_N: pygame.K_n,
    pygame.KSCAN_F1: pygame.K_F1, pygame.KSCAN_F2: pygame.K_F2,
    pygame.KSCAN_F3: pygame.K_F3, pygame.KSCAN_F11: pygame.K_F11,
    pygame.KSCAN_RETURN: pygame.K_RETURN, pygame.KSCAN_KP_ENTER: pygame.K_KP_ENTER,
    pygame.KSCAN_ESCAPE: pygame.K_ESCAPE, pygame.KSCAN_SPACE: pygame.K_SPACE,
    pygame.KSCAN_TAB: pygame.K_TAB,
}
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
SCORE_FILE = Path(__file__).resolve().parent.parent / ".save" / "highscore.json"


def control_key(event: pygame.event.Event) -> int:
    """Use physical controls even when a layout/IME changes the key symbol."""
    key = SCAN_TO_KEY.get(getattr(event, "scancode", None), getattr(event, "key", 0))
    if ord("A") <= key <= ord("Z"):
        key += ord("a") - ord("A")
    if not key:
        symbol = getattr(event, "unicode", "").lower()
        if len(symbol) == 1 and "a" <= symbol <= "z":
            key = ord(symbol)
    return key


def map_fingerprint(game: Game) -> str:
    tiles = bytes(value for tile in sorted(game.maze.floors) for value in tile)
    return hashlib.sha256(tiles).hexdigest()


def read_high_score(path: Path = SCORE_FILE) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("high_score", 0)
        return value if type(value) is int and 0 <= value <= 999999999 else 0
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def save_high_score(score: int, path: Path = SCORE_FILE) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"high_score": score}) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


class App:
    def __init__(self, options):
        self.options = options
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("PAC-MAN | Greedy Ghost")
        self.window_size = (SCREEN[0] * options.scale, SCREEN[1] * options.scale)
        if not options.headless:
            info = pygame.display.Info()
            fit = max(1, min(options.scale, info.current_w // SCREEN[0],
                             max(1, info.current_h - 80) // SCREEN[1]))
            self.window_size = (SCREEN[0] * fit, SCREEN[1] * fit)
        self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        pygame.key.set_repeat(0)
        pygame.key.stop_text_input()
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(icon, (255, 235, 0), (16, 16), 14)
        pygame.draw.polygon(icon, BLACK, ((16, 16), (32, 6), (32, 26)))
        pygame.display.set_icon(icon)
        self.renderer = Renderer()
        self.audio = Audio(options.mute or options.headless)
        self.high_score = 0 if options.no_save else read_high_score()
        self.saved_score = self.high_score
        self.game: Game | None = None
        self.customization = Customization() if options.no_save else read_customization()
        self._seen_maps = {self.customization.last_map} if self.customization.last_map else set()
        self._used_seeds: set[int] = set()
        self._initial_seed = options.seed
        self._held_keys: set[int] = set()
        self.rng_memory = FrightRandom.from_path(options.rng_rom).memory if options.rng_rom else None
        self.running = True
        self.paused = False
        self.help_open = False
        self.fullscreen = False
        self.crt = False
        self.targets = self.customization.show_targets
        self.custom_open = False
        self.custom_page = "options"
        self.menu_index = 0
        self.title_selection = 0
        self.notice: str | None = None
        self.learning_open = False
        self.learning = LearningPlayer()
        self._learning_return = (False, False, False, "options", 0)
        self._custom_was_paused = False
        self._help_was_paused = False
        self.tick_count = 0
        self.frame_count = 0
        if getattr(options, "learn", False):
            self.open_learning()
        elif options.play or options.autoplay or (options.headless and not options.title):
            self.start(self._take_initial_seed())

    def _take_initial_seed(self) -> int | None:
        seed, self._initial_seed = self._initial_seed, None
        return seed

    def _save_customization(self) -> None:
        if not self.options.no_save:
            save_customization(self.customization)

    def start(self, seed: int | None = None, *, immediate: bool = False) -> None:
        if self.game is not None:
            self.high_score = max(self.high_score, self.game.score)
            self._seen_maps.add(map_fingerprint(self.game))
            self._used_seeds.add(self.game.maze.seed)
        candidate = secrets.randbits(32) if seed is None else seed & 0xFFFFFFFF
        # Explicit seeds are a replay tool. Every ordinary UI restart must
        # produce different geometry, even if entropy repeats a prior value.
        while True:
            if seed is None and candidate in self._used_seeds:
                candidate = (candidate + 0x9E3779B9) & 0xFFFFFFFF
                continue
            game = Game(candidate, FrightRandom(self.rng_memory), self.customization.enabled_ghosts)
            fingerprint = map_fingerprint(game)
            if seed is not None or fingerprint not in self._seen_maps:
                break
            candidate = (candidate + 0x9E3779B9) & 0xFFFFFFFF
        self.game = game
        self._recorded_maze = game.maze
        self._used_seeds.add(candidate)
        self._seen_maps.add(fingerprint)
        self.customization.last_map = fingerprint
        self._save_customization()
        if immediate:
            self.game.phase = Phase.PLAYING
            self.game.phase_ticks = 0
            self.game.drain_events()
        self.paused = False
        self.help_open = False
        self.custom_open = False
        self.learning_open = False
        self.notice = None
        if self.audio.available:
            pygame.mixer.stop()
            self.audio.loop_name = None

    def open_customization(self) -> None:
        self._custom_was_paused = self.paused
        self.custom_open = True
        self.custom_page = "options"
        self.menu_index = 0
        self.help_open = False
        self.paused = True

    def close_customization(self) -> None:
        self.custom_open = False
        self.notice = None
        self.paused = self._custom_was_paused if self.game is not None else False

    def open_learning(self) -> None:
        if self.learning_open:
            return
        self._learning_return = (self.paused, self.help_open, self.custom_open, self.custom_page, self.menu_index)
        self.learning_open = True
        self.paused = True
        self.help_open = self.custom_open = False
        self.renderer.buttons = {}

    def close_learning(self) -> None:
        self.learning_open = False
        (self.paused, self.help_open, self.custom_open,
         self.custom_page, self.menu_index) = self._learning_return
        self.renderer.buttons = {}

    def _learning_action(self, action: str) -> None:
        if action.startswith("chapter:"):
            self.learning.select(int(action.split(":")[1]))
        elif action == "previous":
            self.learning.select(self.learning.index - 1)
        elif action == "next":
            self.learning.select(self.learning.index + 1)
        elif action == "play":
            self.learning.playing = not self.learning.playing
        elif action == "replay":
            self.learning.replay()
            self.learning.scroll_line = 0
        elif action == "step":
            if self.learning.details_open:
                self.learning.scroll_line += 8
            else:
                self.learning.step()
        elif action == "speed":
            self.learning.change_speed()
        elif action == "detail":
            self.learning.details_open = not self.learning.details_open
        elif action == "animation":
            self.learning.details_open = False
        elif action == "close":
            self.close_learning()

    def _learning_key(self, key: int) -> None:
        if key in (pygame.K_l, pygame.K_ESCAPE):
            self.close_learning()
        elif key in (pygame.K_TAB, pygame.K_F1, pygame.K_h):
            self._learning_action("detail")
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._learning_action("previous")
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._learning_action("next")
        elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            down = key in (pygame.K_DOWN, pygame.K_s)
            if self.learning.details_open:
                self.learning.scroll_line = max(0, self.learning.scroll_line + (3 if down else -3))
            else:
                self._learning_action("next" if down else "previous")
        elif key in (*CONFIRM_KEYS, pygame.K_p):
            if self.learning.details_open:
                self.learning.details_open = False
            else:
                self._learning_action("play")
        elif key == pygame.K_r:
            self._learning_action("replay")
        elif key == pygame.K_n:
            self._learning_action("step")
        elif key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.learning.change_speed()
        elif key == pygame.K_MINUS:
            self.learning.change_speed(-1)

    def _toggle_targets(self) -> None:
        self.targets = not self.targets
        self.customization.show_targets = self.targets
        self._save_customization()

    def _custom_choice(self, index: int) -> None:
        if self.custom_page == "ghosts":
            if index == 4:
                self.custom_page = "options"
                self.menu_index = 0
                return
            kind = GhostKind(index)
            self.notice = self.customization.set_ghost(kind, kind not in self.customization.enabled_ghosts)
            if self.game is not None:
                self.game.set_enabled_ghosts(self.customization.enabled_ghosts)
            self._save_customization()
        elif index == 0:
            self.custom_page = "ghosts"
            self.menu_index = 0
        elif index == 1:
            self._toggle_targets()
        elif index == 2:
            self.customization.show_roles = not self.customization.show_roles
            self._save_customization()
        else:
            self.close_customization()

    def _toggle_help(self) -> None:
        if self.help_open:
            self.help_open = False
            self.paused = self._help_was_paused
        else:
            self._help_was_paused = self.paused
            self.help_open = True
            self.paused = True

    def _to_title(self) -> None:
        self.game = None
        self.paused = self.help_open = self.custom_open = self.learning_open = False
        self.notice = None
        self.title_selection = 0
        self.audio.ambience(None)

    def _fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window_size = self.window.get_size()
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        pygame.key.stop_text_input()

    def _event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            self._held_keys.clear()
            if self.game and self.game.phase == Phase.PLAYING and not self.options.headless and not self.options.autoplay:
                self.paused = True
        elif event.type == pygame.WINDOWFOCUSGAINED:
            pygame.key.stop_text_input()
        elif event.type == pygame.MOUSEWHEEL and self.learning_open and self.learning.details_open:
            self.learning.scroll_line = max(0, self.learning.scroll_line - event.y * 3)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            viewport = self._viewport()
            if viewport.collidepoint(event.pos):
                x = (event.pos[0] - viewport.x) * SCREEN[0] / viewport.width
                y = (event.pos[1] - viewport.y) * SCREEN[1] / viewport.height
                for action, rect in self.renderer.buttons.items():
                    if rect.collidepoint(x, y):
                        self._click_action(action)
                        break
        elif event.type == pygame.KEYUP:
            self._held_keys.discard(control_key(event))
        elif event.type == pygame.KEYDOWN:
            key = control_key(event)
            if key not in KEYS and (getattr(event, "repeat", False) or key in self._held_keys):
                return
            self._held_keys.add(key)
            self._key(key)

    def _key(self, key: int) -> None:
        if key == pygame.K_q:
            self.running = False
        elif key == pygame.K_F11:
            self._fullscreen()
        elif self.notice is not None:
            if key in (*CONFIRM_KEYS, pygame.K_ESCAPE):
                self.notice = None
        elif self.learning_open:
            self._learning_key(key)
        elif key == pygame.K_l:
            self.open_learning()
        elif self.custom_open:
            rows = 5 if self.custom_page == "ghosts" else 4
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % rows
            elif key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
                self.menu_index = (self.menu_index + 1) % rows
            elif key in (*CONFIRM_KEYS, pygame.K_LEFT, pygame.K_RIGHT):
                self._custom_choice(self.menu_index)
            elif key in (pygame.K_ESCAPE, pygame.K_c):
                if self.custom_page == "ghosts":
                    self.custom_page = "options"
                    self.menu_index = 0
                else:
                    self.close_customization()
        elif key in CONFIRM_KEYS:
            # A finished life takes precedence over help/pause overlays.
            ended = self.game is not None and (self.game.phase == Phase.GAME_OVER or
                    (self.game.phase == Phase.DYING and self.game.lives <= 1))
            if ended:
                self.start(immediate=True)
            elif self.paused or self.help_open:
                self.paused = self.help_open = False
            elif self.game is None:
                if self.title_selection == 1:
                    self.open_customization()
                elif self.title_selection == 2:
                    self.open_learning()
                else:
                    self.start(self._take_initial_seed())
            elif self.game.phase == Phase.READY:
                self.game.phase = Phase.PLAYING
                self.game.phase_ticks = 0
        elif key == pygame.K_c:
            self.open_customization()
        elif key in (pygame.K_F1, pygame.K_h):
            self._toggle_help()
        elif key in (pygame.K_p, pygame.K_PAUSE, pygame.K_ESCAPE):
            if self.help_open:
                self.help_open = False
                self.paused = self._help_was_paused if key == pygame.K_ESCAPE else False
            elif self.game is not None:
                self.paused = not self.paused
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif key == pygame.K_m:
            self.audio.toggle()
        elif key == pygame.K_F2:
            self.crt = not self.crt
        elif key == pygame.K_F3:
            self._toggle_targets()
        elif key == pygame.K_r:
            self.start(self._take_initial_seed() if self.game is None else None, immediate=True)
        elif self.game is None and key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):
            self.title_selection = (self.title_selection + (-1 if key == pygame.K_UP else 1)) % 3
        elif key in KEYS and self.game is not None and not self.paused:
            self.game.steer(KEYS[key])

    def _click_action(self, action: str) -> None:
        if self.notice is not None:
            if action == "notice_ok":
                self.notice = None
        elif action.startswith("learn:") and self.learning_open:
            self._learning_action(action.removeprefix("learn:"))
        elif action == "learn":
            self.open_learning()
        elif action.startswith("choice:"):
            self.menu_index = int(action.split(":")[1])
            self._custom_choice(self.menu_index)
        elif action == "custom":
            self.open_customization()
        elif action == "start":
            self.start(self._take_initial_seed(), immediate=self.game is not None)
        elif action in ("resume", "close_help"):
            self.paused = self.help_open = False
        elif action == "restart":
            self.start(immediate=True)
        elif action == "pause":
            self._key(pygame.K_p)
        elif action == "help":
            self._toggle_help()
        elif action == "sound":
            self.audio.toggle()
        elif action == "title":
            self._to_title()

    def _tick(self) -> None:
        self.tick_count += 1
        if self.learning_open:
            self.learning.tick()
        if self.game is not None and not self.paused:
            if self.options.autoplay:
                self.game.demo_steer()
            self.game.tick()
            if self.game.maze is not self._recorded_maze:
                fingerprint = map_fingerprint(self.game)
                self._seen_maps.add(fingerprint)
                self._used_seeds.add(self.game.maze.seed)
                self.customization.last_map = fingerprint
                self._recorded_maze = self.game.maze
                self._save_customization()
            for event in self.game.drain_events():
                self.audio.play(event)
            self.high_score = max(self.high_score, self.game.score)
        ambience = None
        if self.game is not None and not self.paused and self.game.phase == Phase.PLAYING and self.game.active_ghosts:
            if any(g.state == GhostState.EYES for g in self.game.active_ghosts):
                ambience = "eyes"
            else:
                ambience = "fright" if self.game.fright_left else "siren"
        self.audio.ambience(ambience)
        if self.paused and self.audio.available:
            pygame.mixer.Channel(3).stop()

    def _draw(self) -> pygame.Surface:
        if self.learning_open:
            canvas = self.renderer.draw_learning(self.learning)
        elif self.game is None:
            canvas = self.renderer.draw_title(self.tick_count, self.high_score, self.audio.muted,
                                               self.customization, self.title_selection)
        else:
            canvas = self.renderer.draw_game(self.game, self.high_score, self.targets)
        if self.learning_open:
            pass
        elif self.custom_open:
            canvas = self.renderer.draw_customization(self.customization, self.custom_page, self.menu_index)
        elif self.paused or self.help_open:
            self.renderer.overlay(self.game, self.help_open, self.audio.muted)
        if self.notice is not None:
            self.renderer.draw_notice(self.notice)
        viewport = self._viewport()
        size = viewport.size
        scaled = pygame.transform.scale(canvas, size)
        if self.crt:
            for y in range(1, size[1], 3):
                pygame.draw.line(scaled, (0, 0, 0), (0, y), (size[0], y), 1)
        self.window.fill(BLACK)
        self.window.blit(scaled, viewport)
        pygame.display.flip()
        return canvas

    def _viewport(self) -> pygame.Rect:
        width, height = self.window.get_size()
        scale = min(width / SCREEN[0], height / SCREEN[1])
        if scale >= 1:
            scale = int(scale)
        size = (max(1, int(SCREEN[0] * scale)), max(1, int(SCREEN[1] * scale)))
        return pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)

    def run(self) -> int:
        clock = pygame.time.Clock()
        accumulator = 0.0
        canvas = self.renderer.canvas
        try:
            while self.running:
                for event in pygame.event.get():
                    self._event(event)
                if self.options.headless:
                    self._tick()
                else:
                    accumulator += min(clock.tick(120) / 1000., .25)
                    while accumulator >= 1 / FPS:
                        self._tick()
                        accumulator -= 1 / FPS
                canvas = self._draw()
                self.frame_count += 1
                if self.options.frames is not None and self.frame_count >= self.options.frames:
                    break
            if self.options.screenshot:
                path = self.options.screenshot.resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(pygame.transform.scale(canvas, (SCREEN[0] * 3, SCREEN[1] * 3)), str(path))
                print(f"Screenshot: {path}")
            if self.options.headless and self.game is not None:
                game = self.game
                print(f"seed=0x{game.seed:08X} level={game.level} score={game.score} "
                      f"lives={game.lives} phase={game.phase.value} frames={self.frame_count}")
        finally:
            if not self.options.no_save and self.high_score > self.saved_score:
                save_high_score(self.high_score)
            pygame.quit()
        return 0
