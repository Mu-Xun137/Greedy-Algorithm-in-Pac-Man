"""User preferences and the directed Inky -> Blinky dependency."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable

from .rules import GhostKind

ALL_GHOSTS = frozenset(GhostKind)
GHOST_ROLES = ("追踪者", "伏击者", "夹击者", "游离者")
GHOST_COLORS = ("红鬼", "粉鬼", "蓝鬼", "橙鬼")
GHOST_NAMES = ("BLINKY", "PINKY", "INKY", "CLYDE")
SETTINGS_FILE = Path(__file__).resolve().parent.parent / ".save" / "customization.json"


def valid_ghosts(kinds: Iterable[GhostKind]) -> frozenset[GhostKind]:
    enabled = {GhostKind(kind) for kind in kinds}
    if GhostKind.BLINKY not in enabled:
        enabled.discard(GhostKind.INKY)
    return frozenset(enabled)


@dataclass
class Customization:
    enabled_ghosts: frozenset[GhostKind] = field(default_factory=lambda: ALL_GHOSTS)
    show_targets: bool = False
    show_roles: bool = True
    last_map: str | None = None

    def __post_init__(self) -> None:
        self.enabled_ghosts = valid_ghosts(self.enabled_ghosts)

    def set_ghost(self, kind: GhostKind, enabled: bool) -> str | None:
        kinds = set(self.enabled_ghosts)
        notice = None
        if enabled:
            kinds.add(kind)
            if kind == GhostKind.INKY and GhostKind.BLINKY not in kinds:
                kinds.add(GhostKind.BLINKY)
                notice = "蓝鬼需要红鬼的位置。\n已同时开启红鬼。"
        else:
            kinds.discard(kind)
            if kind == GhostKind.BLINKY and GhostKind.INKY in kinds:
                kinds.discard(GhostKind.INKY)
                notice = "蓝鬼的夹击依赖红鬼的位置。\n关闭红鬼时，已同时关闭蓝鬼。"
        self.enabled_ghosts = frozenset(kinds)
        return notice


def read_customization(path: Path = SETTINGS_FILE) -> Customization:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return Customization()
        states = data.get("ghosts", [True] * 4)
        if not isinstance(states, list) or len(states) != 4 or any(type(v) is not bool for v in states):
            states = [True] * 4
        last_map = data.get("last_map")
        return Customization(
            frozenset(kind for kind in GhostKind if states[kind]),
            data.get("show_targets") is True,
            data.get("show_roles", True) is not False,
            last_map if isinstance(last_map, str) and len(last_map) == 64 else None,
        )
    except (OSError, ValueError, TypeError):
        return Customization()


def save_customization(settings: Customization, path: Path = SETTINGS_FILE) -> None:
    data = {
        "ghosts": [kind in settings.enabled_ghosts for kind in GhostKind],
        "show_targets": settings.show_targets,
        "show_roles": settings.show_roles,
        "last_map": settings.last_map,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass
