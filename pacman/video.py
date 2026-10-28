"""Procedural low-resolution sprites, wall contours and a bitmap typeface."""

from functools import lru_cache
import math
from pathlib import Path

import pygame

from .engine import Game, Phase
from .customization import Customization, GHOST_COLORS, GHOST_NAMES, GHOST_ROLES
from .maze import HEIGHT, TILE, WIDTH
from .rules import Direction, GhostKind, GhostState, Mode, frightened_flash

SCREEN = (224, 304)
MAZE_Y = 24
BLACK = (0, 0, 0)
WHITE = (255, 255, 238)
YELLOW = (255, 235, 0)
BLUE = (33, 33, 255)
CYAN = (0, 255, 255)
PEACH = (255, 184, 151)
COLORS = ((255, 0, 0), (255, 184, 255), (0, 255, 255), (255, 184, 82))

# A complete small display alphabet; no system font or downloaded assets.
_FONT_ROWS = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01111 10000 10000 10000 10000 10000 01111",
    "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01111 10000 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "11111 00100 00100 00100 00100 00100 11111",
    "J": "00111 00010 00010 00010 10010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 10000 11110 00001 00001 11110",
    "6": "01110 10000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00001 01110",
    "!": "00100 00100 00100 00100 00100 00000 00100",
    "?": "01110 10001 00001 00010 00100 00000 00100",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    "/": "00001 00010 00010 00100 01000 01000 10000",
    ":": "00000 00100 00100 00000 00100 00100 00000",
    ".": "00000 00000 00000 00000 00000 00100 00100",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "<": "00010 00100 01000 10000 01000 00100 00010",
    ">": "01000 00100 00010 00001 00010 00100 01000",
    "=": "00000 00000 11111 00000 11111 00000 00000",
    "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000",
    ",": "00000 00000 00000 00000 00100 00100 01000",
    "*": "00000 10101 01110 11111 01110 10101 00000",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}


@lru_cache(maxsize=512)
def text_image(label: str, color: tuple[int, int, int], scale: int = 1) -> pygame.Surface:
    image = pygame.Surface((max(1, len(label) * 6 - 1) * scale, 7 * scale), pygame.SRCALPHA)
    for index, char in enumerate(label.upper()):
        for y, row in enumerate(_FONT_ROWS.get(char, _FONT_ROWS["?"]).split()):
            for x, bit in enumerate(row):
                if bit == "1":
                    image.fill(color, (index * 6 * scale + x * scale, y * scale, scale, scale))
    return image


def text(surface: pygame.Surface, label: str, x: int, y: int,
         color: tuple[int, int, int] = WHITE, scale: int = 1, center: bool = False) -> None:
    image = text_image(label, color, scale)
    surface.blit(image, (x - image.get_width() // 2 if center else x, y))


@lru_cache(maxsize=8)
def cjk_font(size: int) -> pygame.font.Font:
    path = pygame.font.match_font(["microsoftyahei", "simhei", "notosanscjksc", "wenquanyizenhei"])
    if path is None:
        for candidate in ("C:/Windows/Fonts/msyh.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
            if Path(candidate).is_file():
                path = candidate
                break
    return pygame.font.Font(path, size)


@lru_cache(maxsize=512)
def ui_image(label: str, color: tuple[int, int, int], size: int = 11) -> pygame.Surface:
    if label.isascii() and all(character.upper() in _FONT_ROWS for character in label):
        return text_image(label, color)
    return cjk_font(size).render(label, False, color)


def ui_text(surface: pygame.Surface, label: str, x: int, y: int,
            color: tuple[int, int, int] = WHITE, size: int = 11, center: bool = False) -> None:
    image = ui_image(label, color, size)
    surface.blit(image, (x - image.get_width() // 2 if center else x, y))


def dashed_line(surface: pygame.Surface, color: tuple[int, int, int],
                start: tuple[int, int], end: tuple[int, int], dash: int = 3, gap: int = 3) -> None:
    delta = pygame.Vector2(end) - start
    length = delta.length()
    if not length:
        return
    unit = delta / length
    for distance in range(0, math.ceil(length), dash + gap):
        a = pygame.Vector2(start) + unit * distance
        b = pygame.Vector2(start) + unit * min(distance + dash - 1, length)
        pygame.draw.line(surface, color, (round(a.x), round(a.y)), (round(b.x), round(b.y)))


@lru_cache(maxsize=64)
def pac_sprite(direction: int, mouth: int, radius: int = 7) -> pygame.Surface:
    image = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    angles = (-math.pi / 2, math.pi, math.pi / 2, 0)
    heading = angles[direction]
    opening = mouth * math.pi / 24
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if x * x + y * y > radius * radius:
                continue
            angle = math.atan2(y, x)
            relative = (angle - heading + math.pi) % (2 * math.pi) - math.pi
            if mouth == 0 or abs(relative) >= opening:
                image.set_at((x + radius, y + radius), YELLOW)
    return image


def pac(surface: pygame.Surface, x: int, y: int, direction: Direction = Direction.RIGHT,
        frame: int = 2, radius: int = 7) -> None:
    surface.blit(pac_sprite(direction, frame, radius), (x - radius, y - radius))


@lru_cache(maxsize=128)
def ghost_sprite(kind: int, direction: int, frame: int, scared: bool, flash: bool,
                  eyes_only: bool = False) -> pygame.Surface:
    image = pygame.Surface((14, 14), pygame.SRCALPHA)
    if not eyes_only:
        color = WHITE if flash else BLUE if scared else COLORS[kind]
        rows = ["00000111100000", "00011111111000", "00111111111100", "01111111111110"]
        rows += ["11111111111111"] * 8
        rows += (["11100111100111", "11000011000011"] if frame == 0
                 else ["11111111111111", "00111000011100"])
        for y, row in enumerate(rows):
            for x, bit in enumerate(row):
                if bit == "1":
                    image.set_at((x, y), color)
    if scared and not eyes_only:
        face = (255, 0, 0) if flash else PEACH
        image.fill(face, (3, 5, 2, 2))
        image.fill(face, (9, 5, 2, 2))
        for x in range(2, 12):
            image.set_at((x, 10 + (x % 4 in (0, 3))), face)
    else:
        dx, dy = ((0, -1), (-1, 0), (0, 1), (1, 0))[direction]
        for ex in (2, 8):
            pygame.draw.rect(image, WHITE, (ex, 3, 4, 6), border_radius=1)
            image.fill((33, 33, 255), (ex + 1 + dx, 5 + dy, 2, 3))
    return image


def ghost(surface: pygame.Surface, x: int, y: int, kind: int, direction: int,
          frame: int, scared: bool = False, flash: bool = False, eyes_only: bool = False) -> None:
    surface.blit(ghost_sprite(kind, direction, frame, scared, flash, eyes_only), (x - 7, y - 7))


def fruit(surface: pygame.Surface, x: int, y: int, level: int) -> None:
    red = (255, 0, 0)
    green = (0, 222, 66)
    if level == 1:
        pygame.draw.line(surface, PEACH, (x - 4, y + 1), (x + 2, y - 6))
        pygame.draw.line(surface, PEACH, (x + 4, y + 2), (x + 2, y - 6))
        pygame.draw.circle(surface, red, (x - 4, y + 3), 3)
        pygame.draw.circle(surface, red, (x + 4, y + 4), 3)
        surface.fill(WHITE, (x - 5, y + 1, 1, 1))
        surface.fill(WHITE, (x + 3, y + 2, 1, 1))
    elif level == 2:
        pygame.draw.polygon(surface, red, [(x - 6, y - 3), (x + 6, y - 3), (x + 4, y + 3), (x, y + 7), (x - 4, y + 3)])
        pygame.draw.polygon(surface, green, [(x - 5, y - 4), (x + 5, y - 4), (x, y), (x - 2, y - 6)])
        for px, py in ((-3, 0), (3, 0), (0, 3)):
            surface.set_at((x + px, y + py), WHITE)
    elif level <= 6:
        color = (255, 184, 82) if level <= 4 else red
        pygame.draw.circle(surface, color, (x - 2, y), 5)
        pygame.draw.circle(surface, color, (x + 2, y), 5)
        pygame.draw.line(surface, PEACH, (x, y - 4), (x + 1, y - 7))
        pygame.draw.line(surface, green, (x + 1, y - 6), (x + 5, y - 6), 2)
        surface.fill(WHITE, (x - 4, y - 2, 1, 3))
    elif level <= 8:
        for px, py in ((-3, -3), (3, -3), (-5, 1), (0, 1), (5, 1), (-2, 5), (2, 5)):
            pygame.draw.circle(surface, (184, 70, 255), (x + px, y + py), 2)
        pygame.draw.line(surface, green, (x, y - 6), (x + 5, y - 7), 2)
    elif level <= 10:
        pygame.draw.polygon(surface, BLUE, [(x, y - 7), (x + 3, y), (x + 7, y - 3), (x + 5, y + 5), (x, y + 2), (x - 5, y + 5), (x - 7, y - 3), (x - 3, y)])
        surface.fill(YELLOW, (x - 1, y - 3, 3, 8))
        surface.fill(red, (x - 2, y - 1, 5, 2))
    elif level <= 12:
        pygame.draw.polygon(surface, YELLOW, [(x - 3, y - 6), (x + 3, y - 6), (x + 5, y + 3), (x + 7, y + 5), (x - 7, y + 5), (x - 5, y + 3)])
        surface.fill(WHITE, (x - 3, y - 3, 1, 5))
        surface.fill(PEACH, (x - 1, y + 6, 3, 2))
    else:
        pygame.draw.circle(surface, CYAN, (x, y - 3), 4, 2)
        pygame.draw.line(surface, WHITE, (x, y), (x, y + 7), 2)
        surface.fill(WHITE, (x, y + 4, 4, 2))
        surface.fill(WHITE, (x, y + 7, 3, 1))


def wall_surface(game: Game, color: tuple[int, int, int] = BLUE) -> pygame.Surface:
    maze = game.maze
    result = pygame.Surface((WIDTH * TILE, HEIGHT * TILE))
    result.fill(BLACK)
    open_tiles = maze.floors | maze.house | maze.gates
    for ty in range(HEIGHT):
        for tx in range(WIDTH):
            if (tx, ty) in open_tiles:
                continue
            neighbors = [(nx, ny) for nx in range(tx - 1, tx + 2) for ny in range(ty - 1, ty + 2)
                         if (nx, ny) in open_tiles or nx < 0 or nx >= WIDTH or ny < 0 or ny >= HEIGHT]
            if not neighbors:
                continue
            for y in range(ty * TILE, (ty + 1) * TILE):
                for x in range(tx * TILE, (tx + 1) * TILE):
                    distance = min(
                        max(nx * TILE - x, 0, x - (nx * TILE + 7)) ** 2 +
                        max(ny * TILE - y, 0, y - (ny * TILE + 7)) ** 2
                        for nx, ny in neighbors)
                    if 4 <= distance <= 6:
                        result.set_at((x, y), color)
    pygame.draw.line(result, COLORS[GhostKind.PINKY], (13 * TILE, 12 * TILE + 4), (15 * TILE - 1, 12 * TILE + 4))
    return result


class Renderer:
    def __init__(self):
        # Font objects belong to a pygame font session. Recreating a window
        # after pygame.quit() must not reuse objects from the old session.
        cjk_font.cache_clear()
        ui_image.cache_clear()
        self.canvas = pygame.Surface(SCREEN)
        self.maze_key: frozenset | None = None
        self.walls: pygame.Surface | None = None
        self.white_walls: pygame.Surface | None = None
        self.buttons: dict[str, pygame.Rect] = {}
        self.inky_pivot: tuple[int, int] | None = None

    def button(self, action: str, rect: tuple[int, int, int, int], label: str,
               selected: bool = False, size: int = 11) -> None:
        bounds = pygame.Rect(rect)
        self.buttons[action] = bounds
        pygame.draw.rect(self.canvas, (9, 9, 29) if selected else BLACK, bounds)
        pygame.draw.rect(self.canvas, YELLOW if selected else BLUE, bounds, 1, border_radius=2)
        image = ui_image(label, YELLOW if selected else WHITE, size)
        self.canvas.blit(image, image.get_rect(center=bounds.center))

    def draw_title(self, tick: int, high_score: int, muted: bool,
                   settings: Customization | None = None, selected: int = 0) -> pygame.Surface:
        settings = settings or Customization()
        s = self.canvas
        s.fill(BLACK)
        self.buttons = {}
        text(s, "HIGH SCORE", 112, 6, WHITE, center=True)
        text(s, f"{high_score:06d}", 112, 18, WHITE, center=True)
        text(s, "PAC-MAN", 114, 39, BLUE, 4, center=True)
        text(s, "PAC-MAN", 112, 37, YELLOW, 4, center=True)
        ui_text(s, "经典规则 · 随机迷宫", 112, 77, CYAN, center=True)
        ui_text(s, "鬼的职责" if settings.show_roles else "鬼的名字", 112, 100, WHITE, center=True)
        for i in range(4):
            y = 119 + i * 20
            enabled = GhostKind(i) in settings.enabled_ghosts
            sprite = ghost_sprite(i, Direction.RIGHT, tick // 8 % 2, False, False).copy()
            if not enabled:
                sprite.set_alpha(60)
            s.blit(sprite, (17, y - 4))
            label = f"{GHOST_COLORS[i]} · {GHOST_ROLES[i]}" if settings.show_roles else GHOST_NAMES[i]
            ui_text(s, label, 45, y - 4, COLORS[i] if enabled else (90, 90, 110), 12)
            ui_text(s, "开启" if enabled else "关闭", 178, y - 2, CYAN if enabled else (90, 90, 110), 10)
        self.button("start", (24, 202, 176, 22), "Enter  开始游戏", selected == 0)
        self.button("custom", (24, 228, 176, 22), "C  自定义", selected == 1)
        self.button("learn", (24, 254, 176, 22), "L  学习贪心算法", selected == 2)
        self.button("help", (16, 279, 90, 16), "F1/H 帮助", size=9)
        self.button("sound", (118, 279, 90, 16), "M 声音关" if muted else "M 声音开", size=9)
        text(s, "ARROWS SELECT  ENTER CONFIRM", 112, 297, (142, 142, 168), center=True)
        return s

    def draw_learning(self, player):
        from .learning_view import draw_learning
        return draw_learning(self, player)

    def draw_customization(self, settings: Customization, page: str, selected: int) -> pygame.Surface:
        s = self.canvas
        s.fill(BLACK)
        self.buttons = {}
        ui_text(s, "选择参与游戏的鬼" if page == "ghosts" else "自定义", 112, 25, YELLOW, 16, True)
        ui_text(s, "设置实时生效并自动保存", 112, 52, PEACH, 10, True)
        if page == "ghosts":
            for i in range(4):
                y = 78 + i * 32
                rect = pygame.Rect(16, y, 192, 28)
                self.buttons[f"choice:{i}"] = rect
                pygame.draw.rect(s, (9, 9, 29) if selected == i else BLACK, rect)
                pygame.draw.rect(s, YELLOW if selected == i else BLUE, rect, 1, border_radius=2)
                enabled = GhostKind(i) in settings.enabled_ghosts
                sprite = ghost_sprite(i, Direction.RIGHT, 0, False, False).copy()
                if not enabled:
                    sprite.set_alpha(60)
                s.blit(sprite, (24, y + 7))
                ui_text(s, f"{GHOST_COLORS[i]} · {GHOST_ROLES[i]}", 47, y + 5,
                        COLORS[i] if enabled else (100, 100, 120), 11)
                ui_text(s, "开启" if enabled else "关闭", 177, y + 6, CYAN if enabled else WHITE, 10)
            ui_text(s, "蓝鬼需要红鬼的位置。", 112, 213, PEACH, 10, True)
            ui_text(s, "关闭红鬼会同时关闭蓝鬼。", 112, 228, PEACH, 10, True)
            self.button("choice:4", (40, 250, 144, 23), "返回自定义", selected == 4)
        else:
            rows = (("1  鬼的存在", "选择四种鬼是否参与游戏", "选择"),
                    ("2  追踪目标点", "同色虚线 + 空心方框", "开" if settings.show_targets else "关"),
                    ("3  显示鬼的职责", "开始界面用职责替换名字", "开" if settings.show_roles else "关"))
            for i, (title, description, value) in enumerate(rows):
                y = 82 + i * 46
                rect = pygame.Rect(16, y, 192, 39)
                self.buttons[f"choice:{i}"] = rect
                pygame.draw.rect(s, (9, 9, 29) if selected == i else BLACK, rect)
                pygame.draw.rect(s, YELLOW if selected == i else BLUE, rect, 1, border_radius=2)
                ui_text(s, title, 25, y + 4, WHITE, 12)
                ui_text(s, description, 25, y + 23, (142, 142, 168), 9)
                ui_text(s, value, 177, y + 7, CYAN if value != "关" else PEACH, 11)
            if settings.show_targets:
                ui_text(s, "蓝鬼：空心圆是前方两格取点", 112, 217, CYAN, 9, True)
                ui_text(s, "红鬼→取点→目标均用蓝色虚线", 112, 230, CYAN, 9, True)
            self.button("choice:3", (40, 245, 144, 24), "完成 · 返回", selected == 3)
        ui_text(s, "↑↓ 选择 · Enter 切换 · Esc 返回", 112, 290, WHITE, 9, True)
        return s

    def draw_notice(self, message: str) -> None:
        s = self.canvas
        shade = pygame.Surface(SCREEN, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 205))
        s.blit(shade, (0, 0))
        pygame.draw.rect(s, BLACK, (12, 99, 200, 112))
        pygame.draw.rect(s, YELLOW, (12, 99, 200, 112), 1, border_radius=3)
        ui_text(s, "依赖提示", 112, 109, YELLOW, 14, True)
        for i, line in enumerate(message.splitlines()):
            ui_text(s, line, 112, 136 + i * 16, WHITE, 10, True)
        self.buttons = {}
        self.button("notice_ok", (70, 181, 84, 22), "知道了 Enter")

    def draw_targets(self, game: Game) -> list[tuple[tuple[int, int, int], tuple[int, int]]]:
        markers = []
        bounds = pygame.Rect(5, MAZE_Y + 5, SCREEN[0] - 10, HEIGHT * TILE - 10)
        self.inky_pivot = None
        construction = game.inky_construction()
        if construction is not None:
            reference, pivot, target = construction

            def pixel(tile):
                return (tile[0] * TILE + 4, tile[1] * TILE + 4 + MAZE_Y)

            source, middle, destination = map(pixel, (reference, pivot, target))
            player = pixel(game.player.tile)
            for a, b, dash, gap in ((source, middle, 2, 3), (middle, destination, 2, 3),
                                    (player, middle, 1, 2)):
                clipped = bounds.clipline(a, b)
                if clipped:
                    dashed_line(self.canvas, COLORS[GhostKind.INKY], *clipped, dash=dash, gap=gap)
            # An off-board pivot is left off-board; clipping its two vectors
            # preserves the true construction without inventing a midpoint.
            if bounds.collidepoint(middle):
                self.inky_pivot = middle
        for actor in game.active_ghosts:
            target = game.visible_target(actor)
            if target is None:
                continue
            start = (actor.x, actor.y + MAZE_Y)
            destination = (target[0] * TILE + 4, target[1] * TILE + 4 + MAZE_Y)
            clipped = bounds.clipline(start, destination)
            if clipped:
                a, b = clipped
                dashed_line(self.canvas, COLORS[actor.kind], a, b)
                markers.append((COLORS[actor.kind], b))
        return markers

    def draw_game(self, game: Game, high_score: int, targets: bool = False) -> pygame.Surface:
        s = self.canvas
        s.fill(BLACK)
        self.buttons = {}
        if game.maze.floors != self.maze_key:
            self.maze_key = game.maze.floors
            self.walls = wall_surface(game)
            self.white_walls = self.walls.copy()
            self.white_walls.set_colorkey(BLACK)
            pixels = pygame.PixelArray(self.white_walls)
            pixels.replace(BLUE, WHITE)
            del pixels
        text(s, "1UP", 20, 1)
        text(s, "HIGH SCORE", 90, 1)
        text(s, f"{game.score:06d}", 14, 12)
        text(s, f"{max(high_score, game.score):06d}", 108, 12)
        text(s, f"{game.level:02d}", 205, 12, CYAN)
        if game.phase == Phase.CLEAR and game.phase_ticks < 120 and game.phase_ticks // 12 % 2 == 0:
            s.blit(self.white_walls, (0, MAZE_Y))
        else:
            s.blit(self.walls, (0, MAZE_Y))
        for x, y in game.pellets:
            px, py = x * TILE + 4, y * TILE + 4 + MAZE_Y
            if (x, y) in game.powers:
                if game.ticks // 10 % 2 == 0 or game.phase != Phase.PLAYING:
                    pygame.draw.circle(s, PEACH, (px, py), 4)
            else:
                s.fill(PEACH, (px - 1, py - 1, 2, 2))
        markers = self.draw_targets(game) if targets else []
        if game.fruit_ticks:
            fruit(s, game.maze.fruit[0] * TILE + 4, game.maze.fruit[1] * TILE + 4 + MAZE_Y, game.level)
        show_ghosts = game.phase not in (Phase.CLEAR, Phase.GAME_OVER) and not (
            game.phase == Phase.DYING and game.phase_ticks < 85)
        if show_ghosts:
            flash = frightened_flash(game.level, game.fright_left)
            for actor in reversed(game.active_ghosts):
                if actor.state == GhostState.EATEN:
                    continue
                # Direction of the planned turn is visible in their pupils.
                facing = actor.plan if actor.plan is not None else actor.direction
                eyes = actor.state in (GhostState.EYES, GhostState.ENTERING)
                for shift in (-WIDTH * TILE, 0, WIDTH * TILE):
                    ghost(s, actor.x + shift, actor.y + MAZE_Y, actor.kind, facing,
                          game.ticks // 8 % 2, actor.frightened, flash and actor.frightened, eyes)
        player = game.player
        if game.phase != Phase.GAME_OVER and not game.freeze_ticks:
            mouth = (0, 2, 4, 2)[player.distance // 3 % 4] if player.moving else 2
            direction = player.direction
            if game.phase == Phase.DYING and game.phase_ticks < 85:
                direction = Direction.UP
                mouth = min(24, max(1, (85 - game.phase_ticks) // 3))
            if game.phase != Phase.DYING or game.phase_ticks > 10:
                for shift in (-WIDTH * TILE, 0, WIDTH * TILE):
                    pac(s, player.x + shift, player.y + MAZE_Y, direction, mouth)
        if game.popup is not None:
            label, x, y = game.popup
            text(s, label, x, y - 3 + MAZE_Y, CYAN, center=True)
        for color, point in markers:
            pygame.draw.rect(s, color, (point[0] - 4, point[1] - 4, 9, 9), 1)
        if targets and self.inky_pivot is not None:
            pygame.draw.circle(s, COLORS[GhostKind.INKY], self.inky_pivot, 3, 1)
        if game.phase == Phase.READY:
            text(s, "READY!", 112, MAZE_Y + 17 * TILE + 1, YELLOW, center=True)
        elif game.phase == Phase.GAME_OVER:
            text(s, "GAME OVER", 112, MAZE_Y + 17 * TILE + 1, COLORS[0], center=True)
        for i in range(min(game.lives - 1, 6)):
            pac(s, 19 + i * 15, 282, Direction.LEFT, 4, 5)
        for i, level in enumerate(range(game.level, max(0, game.level - 7), -1)):
            fruit(s, 209 - i * 16, 282, level)
        ended = game.phase == Phase.GAME_OVER or (game.phase == Phase.DYING and game.lives <= 1)
        self.button("restart" if ended else "pause", (4, 291, 66, 13), "重开 Enter" if ended else "暂停 P", size=9)
        self.button("custom", (79, 291, 66, 13), "自定义 C", size=9)
        self.button("help", (154, 291, 66, 13), "帮助 F1/H", size=9)
        return s

    def overlay(self, game: Game | None, help_open: bool, muted: bool) -> None:
        s = self.canvas
        shade = pygame.Surface(SCREEN, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 195))
        s.blit(shade, (0, 0))
        self.buttons = {}
        pygame.draw.rect(s, BLACK, (14, 40, 196, 248))
        pygame.draw.rect(s, BLUE, (14, 40, 196, 248), 1, border_radius=5)
        ui_text(s, "操作说明" if help_open else "已暂停", 112, 50, YELLOW, 16, True)
        lines = (("ARROWS/WASD", "移动 / 提前转向"), ("P / ESC", "暂停 / 继续"),
                 ("C", "自定义"), ("R", "新地图并重开"),
                 ("M", "声音关" if muted else "声音开"), ("F2", "CRT 扫描线"),
                 ("F3", "追踪目标开关"), ("F11", "全屏"), ("Q", "退出"))
        for i, (key, action) in enumerate(lines):
            text(s, key, 25, 85 + i * 12, CYAN)
            ui_text(s, action, 112, 82 + i * 12, WHITE, 9)
        ended = game is not None and (game.phase == Phase.GAME_OVER or
                                      (game.phase == Phase.DYING and game.lives <= 1))
        self.button("restart" if ended else "resume", (28, 194, 168, 18),
                    "立即重开 Enter" if ended else "继续游戏 Enter" if game is not None else "返回开始页 Enter")
        self.button("custom", (28, 215, 168, 18), "自定义 C")
        self.button("learn", (28, 236, 168, 18), "学习贪心算法 L")
        self.button("title" if game is not None else "close_help", (28, 257, 168, 18), "返回开始界面" if game is not None else "关闭帮助")
        if game is not None:
            text(s, f"SEED {game.maze.seed:08X}", 112, 277, PEACH, center=True)
