# 验证记录

验证环境：Windows、Python 3.14.0、pygame-ce 2.5.8。日期：2026-10-26。

## 自动检查

执行 `.venv\Scripts\python.exe -m unittest discover -s tests -v`：**60 项测试全部通过**（2.924 秒）。

覆盖内容：

- 1,000 个种子的地图连通性、无死胡同、左右对称、能量豆与禁上路口约束；200 张地图几何均不同；同种子可重现。
- 四鬼目标公式、朝上偏移错误、8 格距离边界、等距转向优先级、禁止主动反向与禁上路口。
- 各阶段散开 / 追逐时序、最后一帧散开、受惊时暂停模式计时、关卡受惊时长、闪烁和 16 帧步长表。
- 个人 / 全局出笼计数、空闲强制出笼、全局计数困鬼行为、红鬼恢复加速等待。
- 吃鬼得分、眼睛回家、复活、普通鬼不穿墙、死亡与过关流程、同种子游戏过程确定性。
- SDL 事件队列中的回车 / 空格开始、方向键 / WASD、暂停与恢复、R 换图、F1 帮助、Q 退出；声音合成与开关；最高分保存及损坏文件恢复。

其他检查：

- `python -m compileall -q main.py pacman tests`：通过。
- `python -m pip check`：`No broken requirements found.`
- 12,000 帧无窗口演示（种子 2026）：成功运行至第 2 关，最终分数 5,440；生命耗尽后进入 GAME OVER，无异常。
- 标题、准备阶段、游玩画面均实际渲染并保存 PNG，经视觉检查无文字遮挡或缺失资源。

## 桌面窗口检查

原生 Windows 游戏窗口可打开，标题页和像素缩放正常显示。系统自动按键注入没有触发可见的开始动作，之后测试窗口已关闭，未完成完整的原生系统键盘链路验证；未把这次自动化现象当成已确认的游戏缺陷。开始与移动等输入路径已由实际 SDL 事件队列集成测试验证。

窗口检查使用 computer-use 技能；临时输入观测脚本和日志已清除。

## 截图复现

```powershell
.\.venv\Scripts\python.exe main.py --headless --seed 42 --frames 1 --screenshot artifacts/ready.png
.\.venv\Scripts\python.exe main.py --headless --seed 42 --autoplay --frames 600 --screenshot artifacts/gameplay.png
.\.venv\Scripts\python.exe main.py --headless --title --frames 1 --screenshot artifacts/title.png
```

复刻范围及随机地图所需的适配详见上级目录 `README.md`。未执行与原版 ROM 的逐帧差分测试。
