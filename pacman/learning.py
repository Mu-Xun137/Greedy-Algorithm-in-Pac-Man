"""Deterministic teaching scenes that share the game's actual AI functions.

The actor choreography slows down and isolates each concept. It is a lesson
board, rather than a second game simulation or a shortest-path solver.
"""

from dataclasses import dataclass
from functools import lru_cache

from .maze import DIRECTIONS, Maze, Tile, adjacent
from .rules import (
    Direction, FrightRandom, GhostKind, Mode, SCATTER_TARGETS,
    choose_direction, inky_target_points, squared_distance, target_tile,
)

LOOP_FRAMES = 480
MOVE_FRAMES = 30
BOARD_COLS = 19
BOARD_ROWS = 11


@dataclass(frozen=True)
class Lesson:
    tab: str
    title: str
    notes: tuple[str, ...]
    details: tuple[str, ...]


LESSONS = (
    Lesson("入门", "贪心：先选眼前最好的一步", (
        "每到路口，只比较下一格的距离。",
        "选眼前最近的一步，不规划全程。",
        "因此可能绕路，并不保证最短路。",
    ), (
        "贪心算法在每次决策时，挑选当前看起来最好的一种选择。吃豆人的鬼把“离目标格更近”当作好坏标准。",
        "在路口，它比较每个可走方向的下一格。平方距离为 d²=(x-Tx)²+(y-Ty)²。开平方不会改变大小顺序，因此可以直接比较平方距离。",
        "动画中的上、左、右分别为 58、80、52，所以选择向右。下方是来路，不能主动掉头，先排除。",
        "这不是提前算好整条最短路线。鬼看不到更远的墙和绕路，所以局部更近的一步，未必带来全局最短路径，甚至可能形成循环。",
        "四只鬼共用这种局部选路；主要区别是目标格 T 怎样产生。后面的四个章节分别展示目标公式。",
    )),
    Lesson("规则", "共同规则：先筛选，再比较", (
        "先排除墙壁和回头方向。",
        "等距时优先：上、左、下、右。",
        "禁上路口也会限制可选方向。",
    ), (
        "先判断下一个路口的出口：墙壁方向不能走，当前行进方向的反方向也不能主动选择。剩下的方向再比较到目标格的平方距离。",
        "两条路距离相同时，依次优先向上、向左、向下、向右。动画会轮流展示等距、墙壁、禁上路口和目标在身后的情况。",
        "鬼会提前一格计划下一个路口的转向，走到那里再执行。玩家临时转向，不能立即改掉鬼已经决定的那一步。",
        "正常追逐和散开时，特殊路口禁止向上转弯；受惊时可忽略该限制。模式切换或吃能量豆发出的反向信号，是“不能主动回头”的例外。",
        "目标格可以在墙里或地图外。它只是方向选择的参考点，并不要求鬼真的能到达那里。",
    )),
    Lesson("红鬼", "红鬼 · 追踪者", (
        "目标就是玩家当前所在的格子。",
        "你一换格，红鬼目标随之改变。",
        "仍按路口贪心选路，不走全局最短路。",
    ), (
        "红鬼 Blinky 的追逐目标最直接：T=玩家当前格。空心方框始终跟着玩家换格，红色虚线连接红鬼与这个目标。",
        "红鬼不会计算一条贯穿整个迷宫的最短路线。它仍然逐个路口进行共同的贪心决策，不能随意掉头。",
        "在常规散开模式中，红鬼以右上方的固定角落为目标。进入 Cruise Elroy 加速阶段后，即使是散开时段，也会继续以玩家为目标。",
        "Cruise Elroy 的两级速度由各关卡的剩余豆数触发。死亡后，红鬼还要等橙鬼出笼才恢复该状态；本项目关闭橙鬼时不会因此卡住红鬼。",
    )),
    Lesson("粉鬼", "粉鬼 · 伏击者", (
        "目标是玩家朝向前方 4 格。",
        "朝向改变，伏击点也跟着改变。",
        "原版朝上时还会向左偏 4 格。",
    ), (
        "粉鬼 Pinky 追的不是玩家当前格，而是玩家朝向前方 4 格：T=P+4D。P 是玩家格，D 是上下左右的单位方向。",
        "这会让粉鬼趋向玩家前方，产生伏击效果。虚线上的小点帮助数出前方四格，空心方框表示真正的目标。",
        "原版存在朝上时的偏移错误。玩家朝上时，目标同时向上 4 格、向左 4 格，而不是正上方 4 格。本项目保留这个行为。",
        "朝上场景里，灰色叉是没有该错误时的理想取点，粉色方框才是实际目标。换个朝向，粉鬼的目标就会明显移动。",
        "决定了目标格以后，粉鬼与红鬼使用完全相同的选路比较、等距优先级和禁止主动回头规则。",
    )),
    Lesson("蓝鬼", "蓝鬼 · 夹击者", (
        "先取玩家前方 2 格为取点 Q。",
        "将红鬼 B 到 Q 的向量放大到两倍。",
        "目标 T=2Q-B；朝上也保留左偏移。",
    ), (
        "蓝鬼 Inky 的目标同时依赖玩家和红鬼。先在玩家前方 2 格取 Q，再以红鬼所在格 B 为起点，把 B→Q 的长度放大到两倍，终点就是 T。",
        "公式是 T=B+2(Q-B)=2Q-B。Q 恰好位于 B 与 T 的中点，B→Q 和 Q→T 的方向与长度相同。",
        "动画中的 B 标在红鬼位置，空心圆 Q 是中间取点，空心方框 T 是最终目标。所有关联虚线保持蓝鬼的颜色；另有蓝鬼自身到 T 的追踪线。",
        "保持玩家不动、移动红鬼，就能看到目标向相反方向移动。因此蓝鬼并不是随机追逐，而是被两个角色的位置共同影响。",
        "玩家朝上时，Q 会同时向上 2 格、向左 2 格。本项目与粉鬼一样保留原版偏移错误。",
        "由于公式读取红鬼坐标，自定义中关闭红鬼会同时关闭蓝鬼。关闭蓝鬼则不需要关闭红鬼。",
    )),
    Lesson("橙鬼", "橙鬼 · 游离者", (
        "距离至少 8 格时，目标是玩家。",
        "不足 8 格时，目标改为散开角落。",
        "去角落途中，也可能与你碰撞。",
    ), (
        "橙鬼 Clyde 先测量自己与玩家的欧氏距离。距离至少 8 格，也就是 d²≥64 时，目标与红鬼一样，是玩家当前格。",
        "距离不足 8 格，即 d²<64 时，目标切换为自己的左下方散开角落。动画中的虚线圆表示 8 格阈值，方框与文字显示当前目标。",
        "距离正好等于 8 格时，仍属于追逐玩家的一侧。不要把这个边界写成“超过 8 格”。",
        "目标切换不意味着立即掉头。橙鬼仍按共同规则继续到路口，选出局部最靠近新目标的方向。",
        "所以它常在靠近玩家后离开，远了又追上来。去角落只是换了目标，并不会让它无害，迎面相撞仍会失去生命。",
    )),
    Lesson("模式", "模式切换：并非总在追逐", (
        "追逐用各自公式，散开去固定角落。",
        "受惊按伪随机方向走，不做贪心。",
        "这里压缩时序，实战按原版计时。",
    ), (
        "四鬼的不同目标公式用于追逐模式。散开模式通常改用各自的固定角落，仍然共享同一套局部选路比较。红鬼的 Elroy 状态是一个例外。",
        "第一关散开/追逐交替时长为 7、20、7、20、5、20、5 秒，之后持续追逐。后续关卡的时序有所变化。",
        "吃能量豆会触发反向。在可受惊的关卡，鬼变蓝并减速，在路口按伪随机方向尝试可行出口，而不是选择离某个目标最近的一格。",
        "受惊会暂停散开/追逐计时。受惊结束时不触发反向；高关卡受惊时间可能为零，但能量豆仍会触发反向。",
        "动画只压缩展示三种行为的区别，不代表真实模式时长。眼睛回家属于另一种状态，本项目为随机迷宫使用保证能回家的距离场。",
    )),
)


@dataclass
class LearningPlayer:
    index: int = 0
    elapsed: float = 0
    playing: bool = True
    speed_index: int = 1
    details_open: bool = False
    scroll_line: int = 0

    @property
    def speed(self) -> float:
        return (.5, 1., 2.)[self.speed_index]

    @property
    def frame(self) -> int:
        return int(self.elapsed) % LOOP_FRAMES

    def tick(self) -> None:
        if self.playing and not self.details_open:
            self.elapsed = (self.elapsed + self.speed) % LOOP_FRAMES

    def select(self, index: int) -> None:
        self.index = index % len(LESSONS)
        self.elapsed = 0
        self.scroll_line = 0

    def replay(self) -> None:
        self.elapsed = 0
        self.playing = True

    def step(self) -> None:
        self.playing = False
        self.elapsed = (self.elapsed + (120 if self.index < 2 else MOVE_FRAMES)) % LOOP_FRAMES

    def change_speed(self, delta: int = 1) -> None:
        self.speed_index = (self.speed_index + delta) % 3


@dataclass(frozen=True)
class DemoActor:
    kind: GhostKind | None
    position: tuple[float, float]
    heading: Direction = Direction.RIGHT
    frightened: bool = False

    @property
    def tile(self) -> Tile:
        return int(self.position[0] + .5), int(self.position[1] + .5)


@dataclass(frozen=True)
class Candidate:
    direction: Direction
    tile: Tile
    distance: int
    blocked: str = ""


@dataclass(frozen=True)
class LessonFrame:
    maze: Maze
    actors: tuple[DemoActor, ...]
    target: Tile | None
    caption: str
    formula: str
    kind: GhostKind = GhostKind.BLINKY
    candidates: tuple[Candidate, ...] = ()
    choice: Direction | None = None
    junction: Tile | None = None
    pivot: Tile | None = None
    reference: Tile | None = None
    ideal: Tile | None = None
    mode: str = "CHASE"


def _maze(floors, no_up=()) -> Maze:
    return Maze(0, frozenset(floors), frozenset(), frozenset(), frozenset(no_up))


OPEN_BOARD = _maze((x, y) for x in range(1, BOARD_COLS - 1) for y in range(1, BOARD_ROWS - 1))
CROSS_FLOORS = frozenset({(x, 6) for x in range(2, 18)} | {(8, y) for y in range(1, 10)})


def _lerp(a, b, fraction):
    return a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction


def _route(points, frame):
    lengths = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:])]
    progress = (frame % LOOP_FRAMES) / LOOP_FRAMES * sum(lengths)
    for a, b, length in zip(points, points[1:], lengths):
        if progress < length:
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            direction = Direction.RIGHT if dx > 0 else Direction.LEFT if dx < 0 else Direction.DOWN if dy > 0 else Direction.UP
            return DemoActor(None, _lerp(a, b, progress / length), direction)
        progress -= length
    return DemoActor(None, points[0])


def _player(index: int, frame: int) -> DemoActor:
    if index in (2, 6):
        return _route(((5, 3), (14, 3), (14, 7), (5, 7), (5, 3)), frame)
    if index == 3:
        case, local = divmod(frame, 120)
        starts = ((6, 6), (11, 8), (12, 5), (8, 3))
        ends = ((10, 6), (11, 6), (8, 5), (8, 5))
        headings = (Direction.RIGHT, Direction.UP, Direction.LEFT, Direction.DOWN)
        return DemoActor(None, _lerp(starts[case], ends[case], local / 119), headings[case])
    if index == 4:
        return DemoActor(None, (9, 6), Direction.RIGHT if frame < 240 else Direction.UP)
    return DemoActor(None, (12, 5), Direction.LEFT)


def _reference(frame: int) -> DemoActor:
    progress = 1 - abs((frame % LOOP_FRAMES) / (LOOP_FRAMES / 2) - 1)
    return DemoActor(GhostKind.BLINKY, (4 + 8 * progress, 6), Direction.RIGHT if frame < 240 else Direction.LEFT)


@lru_cache(maxsize=5)
def _ghost_trace(index: int):
    kind = GhostKind(index - 2) if index < 6 else GhostKind.BLINKY
    tile, heading = ((3, 5), Direction.RIGHT) if index == 5 else ((3, 8), Direction.UP)
    trace = []
    rng = FrightRandom()
    last_mode = "SCATTER" if index == 6 else "CHASE"
    for frame in range(0, LOOP_FRAMES + MOVE_FRAMES, MOVE_FRAMES):
        sample = min(frame, LOOP_FRAMES - 1)
        player = _player(index, sample)
        reference = _reference(sample)
        mode = ("SCATTER", "CHASE", "FRIGHTENED")[min(2, sample // 160)] if index == 6 else "CHASE"
        if mode != last_mode:
            heading = heading.opposite
        frightened = mode == "FRIGHTENED"
        target = target_tile(kind, tile, player.tile, player.heading, reference.tile,
                             Mode.SCATTER if mode == "SCATTER" else Mode.CHASE)
        direction = choose_direction(OPEN_BOARD, tile, heading, target, frightened,
                                     rng.direction() if frightened else 0)
        other = OPEN_BOARD.neighbor(tile, direction)
        trace.append((tile, direction, other))
        tile, heading = other, direction
        last_mode = mode
    return tuple(trace)


def _ghost(index: int, frame: int) -> DemoActor:
    kind = GhostKind(index - 2) if index < 6 else GhostKind.BLINKY
    step, local = divmod(frame, MOVE_FRAMES)
    start, heading, end = _ghost_trace(index)[step]
    return DemoActor(kind, _lerp(start, end, local / MOVE_FRAMES), heading,
                     index == 6 and frame >= 320)


def sample_lesson(index: int, frame: int) -> LessonFrame:
    index %= len(LESSONS)
    frame %= LOOP_FRAMES
    if index < 2:
        junction = (8, 6)
        heading = Direction.UP
        case = frame // 120 if index == 1 else 0
        target = ((15, 2), (15, 2), (8, 1), (8, 9))[case] if index == 1 else (15, 2)
        if index == 1 and case == 0:
            target = (7, 5)
        floors = CROSS_FLOORS - {(8, 5)} if index == 1 and case == 1 else CROSS_FLOORS
        maze = _maze(floors, (junction,) if index == 1 and case == 2 else ())
        choice = choose_direction(maze, junction, heading, target)
        candidates = []
        for direction in Direction:
            tile = adjacent(junction, direction)
            reason = ("墙" if maze.neighbor(junction, direction) is None else
                      "回头" if direction == heading.opposite else
                      "禁上" if junction in maze.no_up and direction == Direction.UP else "")
            candidates.append(Candidate(direction, tile, squared_distance(tile, target), reason))
        if index == 0:
            stage, local = divmod(frame, 120)
            caption = ("① 提前看下一个路口", "② 比较可走邻格的平方距离", "③ 右边 52 最小，先决定向右", "④ 到路口后执行转向")[stage]
            position = ((8, 8 - local / 120) if stage == 0 else (8, 7) if stage < 3
                        else _lerp((8, 7), (10, 6), min(1, local / 90)))
            # The final movement first reaches the junction, then turns.
            if stage == 3:
                position = _lerp((8, 7), junction, min(1, local / 40)) if local < 40 else _lerp(junction, (10, 6), min(1, (local - 40) / 70))
            actor_heading = Direction.RIGHT if stage == 3 and local >= 40 else heading
            formula = "上 58 | 左 80 | 右 52 → 选右"
        else:
            captions = ("等距：上与左都是 1，优先向上", "墙壁：上方不能走，选择向右", "禁上：左右等距，优先向左", "目标在身后，也不能主动掉头")
            caption = captions[case]
            position = _lerp(junction, adjacent(junction, choice), (frame % 120) / 120)
            actor_heading = choice
            formula = "等距优先：上 > 左 > 下 > 右"
        return LessonFrame(maze, (DemoActor(GhostKind.BLINKY, position, actor_heading),), target,
                           caption, formula, candidates=tuple(candidates), choice=choice, junction=junction)

    player = _player(index, frame)
    actor = _ghost(index, frame)
    mode = ("SCATTER", "CHASE", "FRIGHTENED")[min(2, frame // 160)] if index == 6 else "CHASE"
    reference = _reference(frame)
    target = None if mode == "FRIGHTENED" else target_tile(
        actor.kind, actor.tile, player.tile, player.heading, reference.tile,
        Mode.SCATTER if mode == "SCATTER" else Mode.CHASE)
    actors = (actor, player)
    pivot = ideal = reference_tile = None
    if index == 2:
        caption = "玩家一换格，红色目标方框就跟着移动"
        formula = f"T = P = {target}"
    elif index == 3:
        up = player.heading == Direction.UP
        caption = "朝上：实际目标还会左偏 4 格" if up else "小点标出玩家朝向前方的四格"
        dx, dy = DIRECTIONS[player.heading]
        ideal = (player.tile[0] + 4 * dx, player.tile[1] + 4 * dy) if up else None
        formula = f"T = P + 4D{' + 左偏4' if up else ''} = {target}"
    elif index == 4:
        pivot, target = inky_target_points(player.tile, player.heading, reference.tile)
        reference_tile = reference.tile
        actors = (reference, actor, player)
        caption = "红鬼移动，蓝鬼目标反向移动" if player.heading == Direction.RIGHT else "朝上时，取点 Q 还会左偏 2 格"
        formula = f"Q={pivot}  T=2Q-B={target}"
    elif index == 5:
        distance = squared_distance(actor.tile, player.tile)
        far = distance >= 64
        caption = "远：目标是玩家当前格" if far else "近：目标改为左下散开角落"
        formula = f"d²={distance} {'≥' if far else '<'}64 → {'追玩家' if far else '去角落'}"
    else:
        captions = {"SCATTER": "散开：固定角落仍用贪心选路", "CHASE": "追逐：目标改为玩家当前格", "FRIGHTENED": "受惊：伪随机尝试出口，无固定目标"}
        caption = captions[mode]
        formula = "模式时序已压缩，只演示行为变化"
    return LessonFrame(OPEN_BOARD, actors, target, caption, formula, actor.kind,
                       pivot=pivot, reference=reference_tile, ideal=ideal, mode=mode)
