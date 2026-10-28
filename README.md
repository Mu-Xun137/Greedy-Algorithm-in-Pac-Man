# PAC-MAN · Greedy Ghost

Python / pygame-ce 编写的传统吃豆人游戏。每次新游戏及过关时生成新迷宫，保留黑底、蓝墙、像素角色、闪烁能量豆和街机合成音效。

## 学习模块（2026-10-28）

点击开始页的 **“学习贪心算法”**，或按 **L** 进入；暂停 / 帮助页也提供入口。学习期间当前游戏暂停，返回后恢复进入前的状态，保留地图、得分与自定义选择。

共 7 章：贪心入门、共同选路规则、红鬼追踪者、粉鬼伏击者、蓝鬼夹击者、橙鬼游离者、散开 / 追逐 / 受惊。四鬼共享贪心选路，主要区别是目标格公式，模块会把这两层分开讲解。

- **Space / P**：播放或暂停；**N**：单步；**R**：重播。
- **左右方向键**或顶部章节按钮：切换章节。
- **Tab / F1 / H**：切换动画与详解；详解中用上下方向键或滚轮翻阅。
- **速度按钮 / + / -**：0.5×、1×、2×。
- **Esc / L**：返回进入前的界面。

动画使用游戏同一套目标格公式与方向比较函数，以教学速度展示；不模拟完整实战计时。蓝鬼保留“红鬼 B → 空心圆取点 Q → 空心方框目标 T”的同色连线；粉鬼展示朝上偏移错误，橙鬼展示 8 格阈值。

可在游戏外阅读 [图文学习指南与动图](docs/learning.md)。7 个 GIF 位于 `artifacts/learning/`；游戏内演示实时绘制，启动时不依赖 GIF 文件或 Pillow。

```powershell
# 直接进入学习模块
.\.venv\Scripts\python.exe main.py --learn

# 可选：重新导出动图（需要 pygame-ce 与 Pillow）
python -m pip install -r requirements-export.txt
python tools/export_learning.py --all --cleanup
```

也可分别用有 pygame-ce 的解释器执行 `--render`、有 Pillow 的解释器执行 `--encode --cleanup`。生成器会校验循环时长，并将解码后的 GIF 与源帧比较。

## 2026-10-27 更新

- 新局按地图几何去重，并记录上一张地图，避免重开复用相同迷宫。命令行 `--seed` 只用于首次指定地图，之后从界面重开仍会换图。
- 重写按键处理：使用物理扫描码并兼容大小写，关闭游戏中的输入法文字编辑，过滤长按重复切换。P 暂停、F1/H 帮助均提供鼠标按钮入口。
- 游戏结束时 Enter 优先重开，可直接打断最后一次死亡动画，并立即开始新局，不再先消耗一次 Enter 关闭帮助或暂停层。
- 增加“自定义”菜单，包含鬼的存在、追踪目标点和职责显示三个选项。设置实时生效并自动保存。

## 自定义

在开始界面点击 **“自定义”**，或在标题页 / 游戏中按 **C**。也可从暂停与帮助页进入。菜单支持鼠标点击、方向键选择、Enter / 空格切换、Esc 返回。

1. **鬼的存在**：独立控制四种鬼是否参与游戏，也允许全部关闭。关闭蓝鬼保留红鬼；关闭红鬼会同时关闭依赖其坐标的蓝鬼，并弹出提示。重新开启蓝鬼时，如果红鬼已关闭，会连同开启红鬼并解释依赖。关闭的鬼不渲染、不移动、不参与碰撞或出笼计数。
2. **追踪目标点**：开启后，正常追逐和散开状态的鬼会延伸同色虚线到当前追踪目标，目标用空心方框标出。蓝鬼追逐时额外显示“红鬼所在格 → 玩家前方两格取点 → 蓝鬼目标”的辅助虚线，全部沿用蓝鬼颜色；另有玩家到取点的短虚线，中间取点用空心圆表示，取点到两端的向量等长。向上时保留原版的左偏移错误。目标公式每帧更新；受惊随机转向和眼睛回家没有这类贪心目标，不显示误导目标。原版算法允许目标落在地图外，此时虚线沿真实方向延伸到边界，方框在边界显示；出界的中间取点不伪造为地图内的点。
3. **显示鬼的职责**：默认开启，开始界面用“红鬼—追踪者、粉鬼—伏击者、蓝鬼—夹击者、橙鬼—游离者”替换名字；关闭可查看原来的名字。

自定义设置存于 `.save/customization.json`，新局与下次启动均保留。

本次修复验证结果见 [`artifacts/verification_20261027.md`](artifacts/verification_20261027.md)，菜单与蓝鬼辅助连线预览位于 `artifacts/`。

## 直接启动

Windows 双击 **`Start-Game.bat`** 即可。当前项目已安装独立的 `.venv` 环境。

换一台电脑时，需要 Python 3.11 或以上；启动脚本会在项目内创建虚拟环境并安装 `requirements.txt`。也可以手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

不需要另行准备图片或声音资源包。英文字体、精灵与音效由代码生成；中文菜单使用系统微软雅黑或可用的 CJK 字体。缺少音频设备时仍可游玩。

## 操作

| 按键 | 功能 |
| --- | --- |
| Enter / 空格 | 开始游戏；跳过准备等待；继续；结束时立即重开 |
| 方向键 / WASD | 移动，可提前输入下个路口的转向 |
| P / Esc | 暂停或继续；标题页 Esc 退出 |
| R | 重新开始，生成新地图 |
| C | 打开 / 返回自定义菜单 |
| L | 打开 / 返回学习模块 |
| M | 声音开关 |
| F1 / H | 帮助 |
| F2 | CRT 扫描线开关 |
| F3 | 同色虚线与空心方框追踪目标开关 |
| F11 | 全屏 / 窗口 |
| Q | 退出 |

切换到其他窗口时自动暂停。窗口使用整数倍像素缩放，调整大小时保留画面比例。

初始 3 条命，10,000 分奖励一次额外生命。小豆 10 分、能量豆 50 分，同一个能量豆连续吃鬼依次获得 200 / 400 / 800 / 1600 分。水果按关卡增加分值。吃完所有豆子进入下一张随机地图；失去生命保留当前地图与已吃豆子。

最高分保存在项目内的 `.save/highscore.json`，重开游戏后保留。

## 鬼的行动规则

基准为 **1980 年 Pac-Man 街机正常难度**。核心模拟独立于 pygame，以每秒 60 次固定更新执行。追逐中的鬼没有全局最短路径能力。

| 鬼 | 追逐目标 |
| --- | --- |
| 红鬼 Blinky | 玩家当前所在格 |
| 粉鬼 Pinky | 玩家朝向前方 4 格；朝上时同时向左偏移 4 格，保留原版错误 |
| 青鬼 Inky | 取玩家前方 2 格，以红鬼位置为起点将向量延伸 2 倍；保留朝上时的左偏移 |
| 橙鬼 Clyde | 距离玩家至少 8 格时追玩家；不足 8 格时转向自己的散开角落 |

共同规则：

- 提前一格决定下个路口的方向，比较候选格到目标格的欧氏距离平方；等距时按 **上、左、下、右** 排序。
- 正常转向不允许掉头；散开 / 追逐切换和吃能量豆时产生延迟反向信号；受惊结束不触发反向。
- 第一关散开 / 追逐时序为 `7 / 20 / 7 / 20 / 5 / 20 / 5 / 无限` 秒；第二至四关及第五关以后的长追逐和最后一帧散开分别使用对应时序。
- 受惊期间暂停散开 / 追逐计时；按关卡缩短受惊时间，后期能量豆只使鬼反向。临近结束每 14 帧切换闪烁颜色。
- 使用 16 帧像素步长表控制普通、受惊、隧道及两级红鬼加速速度。
- 粉、青、橙鬼按个人豆数顺序出笼；死亡后使用 `7 / 17 / 32` 的全局豆数阈值；长时间不吃豆也会强制出笼。保留全局计数超过阈值后可能困住回家鬼的行为。
- 红鬼在剩余豆数达到各关卡阈值时进入 Cruise Elroy；此时散开期间仍追玩家。死亡后等待橙鬼再次出笼才恢复加速。
- 普通鬼在四个特殊路口禁止向上转弯；受惊和回家状态不受此限制。
- 采用同格碰撞判定，保留相邻两格在同一更新中交换位置时的穿身可能。吃鬼显示分数时暂停普通角色，新吃掉的鬼等待分数显示结束再回家。

## 随机迷宫与复刻边界

迷宫为 `28 × 31` 格，左右对称，中央鬼屋与左右穿屏隧道保持稳定。每张图经过连通性、无死胡同、对称性、四个能量豆与禁上路口检查。相同种子可以重现地图。

这是按原版行为规则重写的 Python 游戏，**没有经过原版 ROM 的逐帧差分认证**。以下差异明确保留：

1. 原版受惊随机数会读取 ROM 的前 8192 字节。独立运行时使用自建的确定性数据表；地址递推、方向编码、顺时针重试和每命重置规则相同，具体受惊路线不等同于 ROM。可用 `--rng-rom` 读取自己的原版数据表。
2. 随机地图中，四个禁上路口移植到鬼屋附近与下部对应路口；被吃后仅剩眼睛的鬼使用到鬼屋的距离场，保证任何生成地图都能回家。正常追逐、散开和受惊不使用这条回家寻路逻辑。
3. 转向在格中心执行，保留一格前瞻；未模拟 Z80 指令调度、8 位坐标溢出、原版的全部子像素相位及第 256 关故障。鬼屋座位和出入口适配本项目的中央鬼屋。
4. 随机地图豆数随几何变化，红鬼加速使用原版的绝对剩余豆数阈值。水果停留时间取原版区间的中值 9.5 秒。音效为自行合成的街机风格音效。

因此，四鬼的追踪策略、模式、速度表与出笼机制可对照原版规则检查；**不能把本项目描述为与原版逐帧、逐位一致的模拟器**。加载 ROM 随机表也仅改变受惊随机数据源。

## 可复现运行与验证

```powershell
# 固定初始地图。暂停页显示当前地图种子。
.\.venv\Scripts\python.exe main.py --seed 42

# 可视化目标格：自定义菜单开启，或进入游戏后按 F3。

# 无窗口演示并保存实际游戏帧
.\.venv\Scripts\python.exe main.py --headless --seed 42 --autoplay --frames 1500 --screenshot artifacts/gameplay.png

# 标题页截图
.\.venv\Scripts\python.exe main.py --headless --title --frames 1 --screenshot artifacts/title.png

# 运行测试；仅使用 Python 标准库 unittest
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 通过 SDL 按键流程生成自定义菜单、依赖弹窗和实时目标预览
.\.venv\Scripts\python.exe tools/capture_previews.py

# 可选：读取已有的前 8192 字节内存数据，或含两个 4096 字节文件的目录
.\.venv\Scripts\python.exe main.py --rng-rom path/to/memory.bin
.\.venv\Scripts\python.exe main.py --rng-rom path/to/rom-directory
```

ROM 目录中的文件名应为 `pacman.6e`、`pacman.6f`。项目不附带这些数据。

`--headless` 自动关闭声音、最高分及自定义设置读写；一次渲染推进一次逻辑更新，便于快速复现。`--autoplay` 仅控制演示玩家，鬼的决策与正常游戏完全共用。

## 文件结构

```text
main.py                命令行入口
Start-Game.bat         Windows 双击启动
pacman/maze.py         随机、对称、无死胡同迷宫
pacman/rules.py        目标格、模式时序、速度表、受惊随机数
pacman/engine.py       固定频率模拟、碰撞、计分与鬼屋状态机
pacman/video.py        像素字体、精灵、墙体与界面
pacman/audio.py        合成音效
pacman/app.py          窗口、输入、暂停、全屏与最高分
pacman/customization.py 自定义设置、鬼的依赖关系与保存
pacman/learning.py      章节、教学场景与动画播放状态
pacman/learning_view.py 动画演示与可滚动详解
tests/                地图、鬼规则、游戏进程与 SDL 输入测试
tools/capture_previews.py 菜单交互与实际目标画面截图
tools/export_learning.py 学习模块 GIF 导出与解码校验
artifacts/            实际渲染截图和验证记录
```

## 行为资料

- [Jamey Pittman — The Pac-Man Dossier](https://pacman.holenet.info/)：作者对原版行为的逆向研究，包含目标格、优先级、时序、出笼与参数表。
- [Shaun LeBron — movement tables](https://github.com/masonicGIT/pacman/blob/master/src/Actor.js)：公开记录的 16 帧步长数据。
- [Ghost mode schedules](https://github.com/masonicGIT/pacman/blob/master/src/ghostCommander.js)、[house counters](https://github.com/masonicGIT/pacman/blob/master/src/ghostReleaser.js)、[energizer timings](https://github.com/masonicGIT/pacman/blob/master/src/energizer.js)：用于交叉核对。
- [MAME driver notes](https://github.com/masonicGIT/pacman/blob/master/doc/pacman.c)：原版 ROM 随机表的内存读取范围。

本项目以这些已记录的行为事实为依据独立编写，图像、字体和声音由本项目代码生成。
