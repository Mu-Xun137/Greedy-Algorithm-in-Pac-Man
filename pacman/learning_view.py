"""Small animated lesson boards and scrollable explanations, in arcade style."""

from functools import lru_cache
import math

import pygame

from .learning import BOARD_COLS, BOARD_ROWS, LESSONS, LearningPlayer, sample_lesson
from .maze import DIRECTIONS
from .rules import Direction, GhostKind
from .video import (
    BLACK, BLUE, COLORS, CYAN, PEACH, WHITE, YELLOW,
    dashed_line, ghost, pac, text, ui_image, ui_text,
)

BOARD = pygame.Rect(12, 85, 200, 112)
CELL = 10
ORIGIN = (17, 86)
GREEN = (83, 255, 150)
GRAY = (111, 119, 146)


def _point(tile):
    return round(ORIGIN[0] + tile[0] * CELL + 5), round(ORIGIN[1] + tile[1] * CELL + 5)


def _line(surface, color, a, b, dash=3, gap=3):
    clipped = BOARD.inflate(-8, -8).clipline(a, b)
    if clipped:
        dashed_line(surface, color, *clipped, dash=dash, gap=gap)
        return clipped[1]
    return None


def _tag(surface, label, position, color):
    image = ui_image(label, color, 9)
    x = max(BOARD.left + 2, min(BOARD.right - image.get_width() - 2, position[0] + 6))
    y = max(BOARD.top + 2, min(BOARD.bottom - image.get_height() - 2, position[1] - 12))
    surface.blit(image, (x, y))


def _circle(surface, center, radius, color):
    for angle in range(0, 360, 12):
        a = math.radians(angle)
        b = math.radians(angle + 5)
        pygame.draw.line(surface, color,
                         (round(center[0] + radius * math.cos(a)), round(center[1] + radius * math.sin(a))),
                         (round(center[0] + radius * math.cos(b)), round(center[1] + radius * math.sin(b))))


def _fit_text(surface, label, x, y, color=WHITE, width=200):
    for size in (10, 9):
        image = ui_image(label, color, size)
        if image.get_width() <= width:
            surface.blit(image, (x, y))
            return
    clipped = surface.get_clip()
    surface.set_clip(pygame.Rect(x, y, width, 14))
    surface.blit(image, (x, y))
    surface.set_clip(clipped)


def draw_board(surface, player: LearningPlayer):
    snapshot = sample_lesson(player.index, player.frame)
    color = COLORS[snapshot.kind]
    previous_clip = surface.get_clip()
    surface.set_clip(BOARD)
    surface.fill(BLACK, BOARD)
    for y in range(BOARD_ROWS):
        for x in range(BOARD_COLS):
            rect = pygame.Rect(ORIGIN[0] + x * CELL, ORIGIN[1] + y * CELL, CELL, CELL)
            if (x, y) not in snapshot.maze.floors:
                pygame.draw.rect(surface, (4, 7, 23), rect)
                pygame.draw.rect(surface, (24, 34, 105), rect, 1)
            else:
                pygame.draw.rect(surface, (11, 17, 42), rect, 1)
    pygame.draw.rect(surface, BLUE, BOARD, 1)

    primary = next(actor for actor in snapshot.actors if actor.kind == snapshot.kind)
    pacman = next((actor for actor in snapshot.actors if actor.kind is None), None)
    if player.index == 5:
        _circle(surface, _point(pacman.tile), 8 * CELL, (116, 79, 36))

    target_point = None
    if snapshot.target is not None:
        target_point = _line(surface, color, _point(primary.position), _point(snapshot.target))
    if player.index == 3 and pacman is not None:
        dx, dy = DIRECTIONS[pacman.heading]
        for step in range(1, 5):
            tile = pacman.tile[0] + step * dx, pacman.tile[1] + step * dy
            pygame.draw.circle(surface, GRAY if snapshot.ideal else color, _point(tile), 1)
        if snapshot.ideal is not None:
            ideal = _point(snapshot.ideal)
            _line(surface, GRAY, _point(pacman.tile), ideal, 1, 2)
            _line(surface, color, ideal, _point(snapshot.target), 2, 2)
            pygame.draw.line(surface, GRAY, (ideal[0] - 3, ideal[1] - 3), (ideal[0] + 3, ideal[1] + 3))
            pygame.draw.line(surface, GRAY, (ideal[0] + 3, ideal[1] - 3), (ideal[0] - 3, ideal[1] + 3))
        else:
            _line(surface, color, _point(pacman.tile), _point(snapshot.target), 1, 2)

    if snapshot.pivot is not None:
        reference, pivot, target = map(_point, (snapshot.reference, snapshot.pivot, snapshot.target))
        _line(surface, color, reference, pivot, 2, 2)
        _line(surface, color, pivot, target, 2, 2)
        _line(surface, color, _point(pacman.tile), pivot, 1, 2)

    for candidate in snapshot.candidates:
        point = _point(candidate.tile)
        selected = candidate.direction == snapshot.choice and (player.index == 1 or player.frame >= 240)
        shade = GREEN if selected else (147, 72, 75) if candidate.blocked else PEACH
        pygame.draw.rect(surface, shade, (point[0] - 4, point[1] - 4, 9, 9), 1)
        if candidate.blocked:
            pygame.draw.line(surface, shade, (point[0] - 2, point[1] - 2), (point[0] + 2, point[1] + 2))
            pygame.draw.line(surface, shade, (point[0] - 2, point[1] + 2), (point[0] + 2, point[1] - 2))
        elif player.index == 1 or player.frame >= 120:
            offset = {Direction.UP: (-5, -15), Direction.LEFT: (-20, -3),
                      Direction.RIGHT: (7, -3), Direction.DOWN: (-5, 8)}[candidate.direction]
            text(surface, str(candidate.distance), point[0] + offset[0], point[1] + offset[1], shade)

    for actor in snapshot.actors:
        position = _point(actor.position)
        if actor.kind is None:
            pac(surface, *position, actor.heading, (0, 2, 4, 2)[player.frame // 5 % 4])
        else:
            ghost(surface, *position, actor.kind, actor.heading, player.frame // 8 % 2, actor.frightened)
    if target_point is not None:
        pygame.draw.rect(surface, color, (target_point[0] - 4, target_point[1] - 4, 9, 9), 1)
        _tag(surface, "角落" if player.index == 5 and snapshot.target != pacman.tile else "T", target_point, color)
    if snapshot.pivot is not None:
        pivot = _point(snapshot.pivot)
        pygame.draw.circle(surface, color, pivot, 3, 1)
        _tag(surface, "Q", pivot, color)
        _tag(surface, "B", _point(snapshot.reference), color)
    surface.set_clip(previous_clip)
    return snapshot


@lru_cache(maxsize=7)
def detail_lines(index: int) -> tuple[str, ...]:
    lines = []
    for paragraph in LESSONS[index].details:
        line = ""
        for character in paragraph:
            if line and ui_image(line + character, WHITE, 11).get_width() > 184:
                lines.append(line)
                line = character
            else:
                line += character
        if line:
            lines.append(line)
        lines.append("")
    return tuple(lines[:-1])


def draw_learning(renderer, player: LearningPlayer):
    surface = renderer.canvas
    surface.fill(BLACK)
    renderer.buttons = {}
    lesson = LESSONS[player.index]
    ui_text(surface, "学习", 12, 5, YELLOW, 14)
    text(surface, f"{player.index + 1:02d}/07", 184, 11, CYAN)
    renderer.button("learn:detail", (119, 3, 58, 19), "动图 Tab" if player.details_open else "详解 Tab", size=9)
    for index, chapter in enumerate(LESSONS):
        renderer.button(f"learn:chapter:{index}", (14 + index * 28, 29, 28, 19), chapter.tab,
                        selected=player.index == index, size=10)
    ui_text(surface, lesson.title, 112, 51, WHITE, 13, True)

    if player.details_open:
        ui_text(surface, "详解 · ↑↓ / 滚轮翻阅", 112, 72, CYAN, 9, True)
        lines = detail_lines(player.index)
        visible = 11
        maximum = max(0, len(lines) - visible)
        player.scroll_line = min(maximum, max(0, player.scroll_line))
        pygame.draw.rect(surface, (5, 7, 19), (12, 87, 200, 175))
        old_clip = surface.get_clip()
        surface.set_clip((17, 91, 187, 167))
        for row, line in enumerate(lines[player.scroll_line:player.scroll_line + visible]):
            ui_text(surface, line, 18, 92 + row * 15, WHITE, 11)
        surface.set_clip(old_clip)
        pygame.draw.line(surface, (30, 39, 80), (207, 91), (207, 255), 2)
        height = max(10, int(164 * min(1, visible / len(lines))))
        y = 91 + int((164 - height) * player.scroll_line / max(1, maximum))
        pygame.draw.rect(surface, CYAN, (206, y, 3, height))
    else:
        snapshot = sample_lesson(player.index, player.frame)
        _fit_text(surface, snapshot.caption, 12, 72, CYAN)
        draw_board(surface, player)
        _fit_text(surface, snapshot.formula, 12, 200, COLORS[snapshot.kind])
        for row, line in enumerate(lesson.notes):
            _fit_text(surface, line, 12, 218 + row * 14)

    renderer.button("learn:previous", (8, 270, 35, 18), "上页", size=9)
    renderer.button("learn:animation" if player.details_open else "learn:play", (47, 270, 64, 18),
                    "看动图 Tab" if player.details_open else "暂停 Space" if player.playing else "播放 Space", size=9)
    renderer.button("learn:next", (115, 270, 35, 18), "下页", size=9)
    renderer.button("learn:close", (154, 270, 62, 18), "返回 Esc", size=9)
    renderer.button("learn:replay", (8, 290, 55, 14), "回页首 R" if player.details_open else "重播 R", size=9)
    renderer.button("learn:step", (67, 290, 61, 14), "翻页 N" if player.details_open else "单步 N", size=9)
    renderer.button("learn:speed", (132, 290, 84, 14), f"速度 {player.speed:g}x", size=9)
    return surface
