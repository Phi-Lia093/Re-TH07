# 文档总索引与阅读顺序

> 本文件告诉你：**先读什么、哪些是权威结论、哪些已被推翻。**

---

> **先读这个**：[`FINAL-STATUS.md`](FINAL-STATUS.md) —— 目标的实际完成度、已解出与未解出的部分。

## 1. 如果你是第一次看这个项目

按这个顺序读：

| 顺序 | 文档 | 为什么先读 |
|------|------|-----------|
| 1 | [`32-gameplay-parameters.md`](32-gameplay-parameters.md) | **所有已确证数值的总表**，最快建立全貌 |
| 2 | [`21-binary-partition-map.md`](21-binary-partition-map.md) | 哪些是游戏代码、哪些是库 |
| 3 | [`15-symbol-recovery-workflow.md`](15-symbol-recovery-workflow.md) | 符号命名规范和当前进度 |
| 4 | 按需查阅下面的分类索引 | |

---

## 2. 按子系统索引

### 2.1 字节码虚拟机（三套）

| 系统 | 文档 | 状态 |
|------|------|------|
| **ECL**（敌机/关卡） | [`01`](01-ecl-format.md) [`02`](02-ecl-instructions.md) [`03`](03-ecl-opcode-table.md) [`23`](23-ecl-control-flow.md) | ✅ 完整 |
| **ANM**（精灵动画） | [`16`](16-anm-opcodes.md) | ✅ 15 opcode 全解 |
| **CAM**（摄像机） | [`22`](22-camera-keyframes.md) | ✅ 主轴完整 |
| **MSG**（对话） | [`34`](34-msg-script-format.md) [`35`](35-msg-opcodes.md) [`36`](36-text-markup.md) | ✅ 15 opcode 全解 |

> **移植陷阱**：CAM 的缓动编号与 ECL/ANM **语义相反**（见 `docs/32` §6.1）。

### 2.2 渲染

| 主题 | 文档 |
|------|------|
| D3D8 初始化、相机、投影 | [`09`](09-rendering-d3d8.md) |
| 绘制循环、顶点格式 | [`10`](10-draw-loop-and-layout.md) |
| ANM 贴图清单 | [`11`](11-anm-atlas-inventory.md) |
| 场景与渲染元素 | [`13`](13-scenes-and-rendering.md) |
| HUD 槽位绑定 | [`26`](26-hud-slots.md) |
| 布局坐标（含截图验证） | [`12`](12-ui-layout.md) [`14`](14-screenshot-verification.md) |

### 2.3 玩法机制

| 机制 | 文档 |
|------|------|
| 运动积分与阻尼 | [`25`](25-motion-integration.md) |
| 玩家状态机（Bomb/无敌） | [`28`](28-player-state-machine.md) [`27`](27-player-bomb.md) |
| Bomb 清屏 | [`29`](29-bomb-bullet-clear.md) |
| 计分公式 | [`33`](33-scoring.md) |
| 道具掉落与收集 | [`30`](30-item-drops.md) [`31`](31-item-collection.md) |
| 慢动作 | [`38`](38-slowmotion.md) |
| **全部 12 个 Bomb** | [`46`](46-all-bombs-complete.md) |
| 主循环与输入 | [`24`](24-main-loop.md) |
| 关卡与实体 | [`18`](18-stage-loop-and-entities.md) |

### 2.4 资源与数据格式

| 格式 | 文档 |
|------|------|
| `.std` 关卡数据 | [`37`](37-std-loader.md) ✅（`05` 已过时） |
| `.sht` 玩家数据 | [`06`](06-player-sht.md) |
| PBG4 封包、音频 | [`19`](19-resources-and-audio.md) |
| `.rpy` 录像 | 见 `docs/11` 的符号表 `11_replay_ui.txt` 与 `24_menu.txt` |

---

## 3. 已被推翻的结论（**不要采信**）

这些是我在过程中犯过并已修正的错误，记录在这里防止重蹈：

| 错误结论 | 实际 | 修正文档 |
|---------|------|---------|
| `FUN_00429c42` 是 `.std` 播放器 | 是 `msgN.dat` 对话脚本 | `34` |
| `.std` 区段 B 是渲染数据 | **区段 A 才是**，B 无消费者 | `37` |
| `FUN_00441960` 是死亡序列 | 是 **Bomb** 序列 | `27` |
| HUD 只有 Graze/Point | 有 **Power/Graze/Point 三项** | `14` |
| Player/Bomb 显示数字 | 显示**星星图标** | `14` |
| 标题菜单 Quit 在第 4 位 | **Quit 在最后** | `14` |
| `0x198f` 是 sprite 索引基址 | 是数值偏移 | 提交记录 |
| `FUN_0041e4b0` 是解锁检查 | 是脚本加载器 | `36` |
| S 字段是 2 字节 | ANM 中是 **4 字节** | `16` |
| `.std` 区段 A 有 19 条 | 实际 **59 条**（`u16[1]` 不是记录数） | `37` |

### 3.1 一个反复出现的错误模式

**「被谁调用」不能作为「它做什么」的证据。**

最少三次踩到这个坑：
- `text_check_unlock`（在 `@F` 分支被调用，实际是文件加载）
- `player_die_sequence`（表现像死亡，实际是 Bomb）
- `.std` 播放器（加载 `.dat`，不是 `.std`）

**正确做法**：读函数体，或用 `tools/field_xref.py` 交叉引用字段。

---

## 4. 已知空白（**实现前必须补查**）

| 项 | 状态 |
|----|------|
| `.std` 区段 B 的消费者 | 发布版中不存在 |
| ~~慢动作是否双重缩放~~ | ✅ **已确证：确实双重生效**（见 `38` §2.1.1） |
| ~~死亡残机扣除~~ | ✅ **已解出**（见 `39`） |
| `0x2000` 道具标志 | 🔶 **赋值条件已解，作用未确认**（见 `41`） |
| ~~樱点计分~~ | ✅ **已解出**（见 `40`） |
| 文字指令 `@c` 的用途 | 未确认 |
| ~~摄像机 VM case 4~~ | ✅ **已解出：两阶段跳转**（见 `22` §9） |

---

## 5. 工具清单

| 工具 | 用途 |
|------|------|
| `tools/batch_review.py` | 批量阅读未命名函数（自动跳过已命名） |
| `tools/dump_batch.py` | 按名字/区间导出函数体 |
| `tools/field_xref.py` | **交叉引用结构偏移**（防误判的关键工具） |
| `tools/symbol_check.py` | 检查符号表重复与冲突（`--fix` 修复） |
| `tools/classify.py` | 按函数体形态分类 |
| `tools/propose_names.py` | 生成命名提案（需人工复核） |
| `tools/ecl_usage.py` | ECL opcode 使用统计 |
| `tools/pbg4.py` / `anm_parse.py` / `sht_parse.py` / `ecl_dump.py` | 各格式解析器 |

---

## 6. 当前进度

| 项 | 数量 |
|----|------|
| 函数总数 | **1327**（`FUN_*`） |
| **已命名游戏函数** | **355 / 693（51.2%）** |
| 已识别库函数 | ~60 |
| 符号总数 | 441（零重复） |
| 文档 | 40 篇（含本索引） |
| 回合数 | 39 |

### 6.1 未覆盖的部分

剩余 **329** 个游戏函数未命名，主要是：
- 特效序列（`0x40xxxx` 区间的 `eff_draw_*` 变体）
- 各 Boss 的专属行为
- UI 的细枝末节

**这些不影响核心玩法逻辑的照抄** —— 核心机制（ECL/ANM/CAM/MSG 四套 VM、运动、计分、Bomb、道具、慢动作）都已解出。
