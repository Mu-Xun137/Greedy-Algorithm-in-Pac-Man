# 2026-10-28 学习模块验证

## 功能

- 开始页增加第三个“学习贪心算法”入口；L 快捷键和暂停 / 帮助页也可进入。
- 共 7 章：贪心入门、共同规则、红鬼、粉鬼、蓝鬼、橙鬼、模式切换。
- 动画支持播放 / 暂停、重播、单步、0.5× / 1× / 2×，各章配有可滚动详解。
- 学习时冻结实战，返回时恢复进入前的暂停、帮助或自定义子菜单状态，保留地图、得分及鬼的开关。
- 场景直接复用 `target_tile`、`choose_direction` 和 `inky_target_points`，不另写一套目标计算。
- 蓝鬼显示 B→Q→T 同色关联线；粉鬼展示朝上偏移与理想取点的区别；橙鬼展示恰好 8 格仍追逐的边界。
- 受惊场景不伪造贪心目标，压缩模式时序在界面与详解中明确说明。

## 自动检查

命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q
```

**125 项测试全部通过，用时 4.186 秒。** 新增覆盖动画时钟、暂停 / 调速 / 单步、示例距离与选择、四鬼目标、橙鬼 8 格边界、蓝鬼向量中点、章节操作、详解滚动、缩放点击、进入与返回状态、实战不被推进及字体会话重建。

Python 编译检查通过；`pip check` 输出 `No broken requirements found.`。`Start-Game.bat --headless --learn --frames 60` 可成功启动学习模块。

## 动图与视觉检查

7 个 GIF 均为 **8,000 ms、无限循环**。每个从 80 张源帧生成，静止的相邻帧可合并时长；解码后帧数分别为 70、65、80、80、80、80、80。

导出器检查循环标记和累计时长，并在第 0、20、40、60、79 个源时间点将 GIF 解码画面逐像素与源 PNG 比较，全部一致。完整清单在 `learning/manifest.json`，临时帧目录在校验通过后已清理。

已检查入门、粉鬼、蓝鬼、橙鬼及蓝鬼详解的实际渲染图，修正了坐标括号、逗号的像素字形，公式不再显示问号。按钮与文章宽度经过自动检查。

原生 Windows 窗口通过 `main.py --learn --scale 2` 打开，已观察到入门页和粉鬼章节正常显示并播放。窗口有人机交互时停止自动输入，以免干扰阅读；章节切换、播放控制及滚动由 SDL 事件测试覆盖。

## 导出复现

```powershell
# 项目虚拟环境有 pygame-ce；系统 Python 有 Pillow 12.0.0
.\.venv\Scripts\python.exe -X utf8 tools/export_learning.py --render
python -X utf8 tools/export_learning.py --encode --cleanup
```

若在一个环境同时安装了 `requirements-export.txt`，可直接执行 `tools/export_learning.py --all --cleanup`。游戏运行仅需要原有的 pygame-ce 依赖。
