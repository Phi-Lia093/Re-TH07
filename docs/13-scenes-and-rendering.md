# TH07 场景与渲染元素全表

> 本文档枚举游戏的**全部场景（Screen）**，以及每个场景的渲染元素。
> 所有结论来自 `th07.exe` 反汇编，标注来源。

---

## 1. 场景状态机（已解出）

### 1.1 引擎的场景切换

顶层对象保存场景号：

```c
// th07.exe.c:26341
FUN_00437903("scene %d -> %d\r\n",
             *(int *)(param_1 + 0x154),   // 当前场景
             *(int *)(param_1 + 0x158));  // 目标场景
```

切换时执行一段 `switch`，把场景号映射到**进入/退出处理函数**。

### 1.2 场景号表

| id | 进入处理 | 说明 |
|----|---------|------|
| 0 | （空闲） | 无场景 |
| 1 | `FUN_0042f45d` + 进入 | |
| 2 | `FUN_0042f3c5` | |
| 3 | `FUN_0042f45d` + `FUN_0042f3c5` | |
| 4 | （仅过渡） | 转场 |
| 5 | `FUN_0044a302` / `FUN_0045c5d0` | |
| 6 | `FUN_0044a302` + `FUN_00443da0` | |
| 7 | `FUN_0045c5d0` + `FUN_00443da0` | |
| 8 | `FUN_0043b4db` | |
| 9 | `FUN_0041e820` | |
| 10 | `FUN_00443da0` + `FUN_0042f3c5` | |
| 11 | `FUN_0042f45d` + `FUN_0042f3c5` | |
| 12 | `FUN_0042f45d` + `FUN_0042f3c5` | |

共 **13 个状态**（0~12），其中 0 为空闲、4 为过渡，**实际内容场景 11 个**。

`FUN_0042f45d` 是几乎所有场景都会先调用的**共享清理函数**。

> **标注**：场景号与具体界面的对应关系尚未完全确证。
> 下面的场景清单基于**资源加载点**（§2）推进，这是更可靠的依据。

---

## 2. 资源槽位表（已完全解出）

TH07 的所有 ANM 通过统一函数加载：

```c
FUN_0044df90(slot, "data/xxx.anm", flags);
```

**槽位号在全局唯一**，所以「加载某槽位的函数」就是该界面的代码。

| 槽 | 资源 | 加载函数 | 归属界面 |
|----|------|---------|---------|
| 0 | `text.anm` | `FUN_00438986` | 文本渲染 |
| **1** | **`ascii.anm`** | `FUN_00401d70` | **全局字体（所有界面共用）** |
| 4 | `capture.anm` | `FUN_00401d70` | 截图保存 |
| 10 | `player00/01/02.anm` | `FUN_004423e0` | 自机 |
| 11 | `etama.anm` | `FUN_00426f60` | 弹幕 |
| 17 | `eff01~05,07` | `FUN_0041cde0` | 特效 |
| 18 | `eff04b,07` | `FUN_0041cde0` | 特效 |
| 19 | `eff06,08` | `FUN_0041cde0` | 特效 |
| 21 | `front.anm` | `FUN_00428b19` | 前景装饰 |
| 23 | `loading*/loading2/3` | `FUN_00428b19` | **读盘画面** |
| 24 | `std1~8txt.anm` | `FUN_00428b19` | **对话文字框** |
| 25 | `face_mr/rm/sk00.anm` | `FUN_00428b19` | 表情立绘 |
| 28 | `face_01~08_00.anm` | `FUN_00428b19` | **关卡立绘** |
| 32 | `title01.anm` | `FUN_0045bf15` | **标题界面** |
| 42 | `result00.anm` | `FUN_00449b05` | **成绩界面** |
| 46 | `music00.anm` | `FUN_0043ae20` | **音乐室** |
| 49 | `staff01.anm` | `FUN_0041e590` | **STAFF ROLL** |

> `FUN_00428b19` 一次性加载了 read/loading、对话文字、立绘 —— 说明
> **游戏主流程（Stage）与对话系统是同一个场景**。

---

## 3. 场景清单（11 个内容场景）

### 3.1 SCENE: TITLE（标题）

| 项 | 内容 |
|----|------|
| 资源 | `title01.anm`（槽 32）、`front.anm`（槽 21） |
| 背景 | `title01` entry0（512×256 主视觉） |
| 菜单 | `title01` entry1（94 个文字 sprite） |
| 前景 | `front.anm`（樱花等装饰） |
| 初始化 | `FUN_0045bf15` |
| 菜单项 | Start / Extra Start / Practice Start / Quit / Replay / Result / Music Room / Option |

**渲染顺序**（推断自资源用途）：
```
1. 背景主视觉 (title01 e0)
2. 前景装饰 (front)
3. 菜单文字 (title01 e1)
```

**选中态**：同 sprite 的 `v + 64`。

---

### 3.2 SCENE: GAME（游戏主流程）

| 项 | 内容 |
|----|------|
| 资源 | `player*.anm`(10)、`etama.anm`(11)、`eff*.anm`(17-19)、`stgNbg.anm`、`stgNenm.anm`、`ascii.anm`(1) |
| 初始化 | `FUN_00428b19`（含读盘）、`FUN_004423e0`（自机）、`FUN_00426f60`（弹幕） |
| HUD | `ascii.anm` 逐字符绘制 |

**渲染层序**（由 z 值决定，见 `docs/09`）：

```
远景背景层   (stgNbg, z 大)
中景背景层   (stgNbg 多层)
敌人         (stgNenm)
敌弹         (etama)
自机         (player)
自机弹       (etama? 或独立)
全屏特效     (eff01~08, 384×448 覆盖层)
HUD          (ascii, z 最小)
```

**HUD 坐标**（已确认）：

| 元素 | 坐标 |
|------|------|
| HUD 区左边界 | **X = 512** |
| 图标行起点 | **X = 496**，间隔 **16** |
| 行 Y | 64 / 96 / 112 / 144 / 160 / 176 / 464 |
| 缩放 | 0.48 / 0.46 |

---

### 3.3 SCENE: LOADING（读盘）

| 项 | 内容 |
|----|------|
| 资源 | `loading.anm` / `loading2` / `loading3`（槽 23） |
| 绘制函数 | `FUN_0042a876` |
| 底图 | **384×448**（单 sprite） |
| 进度条 | 固定坐标，长度 48px 线性增长 |

**进度条几何**（已解出）：

```c
if (frames < 60) bar = ((frames + frac) * 48.0) / 60.0;
else             bar = 48.0;

// 4 顶点三角带
v0 = (SCR_W + 16,          384.0,         0)
v1 = (SCR_W + 384 - 16,    384.0 + bar,   0)
v2 = (SCR_W + 16,          384.0 + bar,   0)
v3 = (SCR_W + 384 - 16,    384.0,         0)
```

---

### 3.4 SCENE: DIALOG（对话）

| 项 | 内容 |
|----|------|
| 资源 | `stdNtxt.anm`(24)、`face_*.anm`(25, 28) |
| 文字框 | `256×48`（std*txt 的 sprite） |
| 立绘 | `126×510`（半身）或 `256×512`（全身） |

---

### 3.5 SCENE: RESULT（成绩查看菜单）

| 项 | 内容 |
|----|------|
| 资源 | `result00.anm`（槽 42） |
| 初始化 | `FUN_00449b05` |
| entry0 | 菜单项（9 个 sprite，256×32） |
| entry1 | 成绩表（8 个 sprite，112×48 / 144×48） |

**菜单项**（从贴图读出）：
```
Easy / Normal / Hard / Lunatic / Extra の記録を見る
御札戦歴を見る
戻る
Phantasm の記録を見る
その他の記録を見る
```

---

### 3.6 SCENE: SCORE TABLE（成绩表）

| 项 | 内容 |
|----|------|
| 绘制函数 | `FUN_00448d40`（主表）、`FUN_0045b5ef`、`FUN_0045b9ad` |
| 表头 | `No.   Name     Date   Player Score` |
| 数据行 | `No.%.2d %8s %5s  %7s %9d0` |
| 排行 | `Stage    HI-Score` / `Stage    LastScore` |

---

### 3.7 SCENE: MUSIC ROOM（音乐室）

| 项 | 内容 |
|----|------|
| 资源 | `music00.anm`（槽 46）、`musiccmt.txt` |
| 初始化 | `FUN_0043ae20` |
| 横幅 | `256×64`（单 sprite） |
| 曲目列表 | 21 首（thbgm 音轨） |
| 评语 | 纯文本（`musiccmt.txt`，6515 字节） |

---

### 3.8 SCENE: STAFF ROLL（结局 STAFF）

| 项 | 内容 |
|----|------|
| 资源 | `staff01.anm`（槽 49） |
| 初始化 | `FUN_0041e590` |
| 布局 | 15 个 sprite：`512×32 ×14` + `512×48` |
| 滚动 | 纵向滚动名单 |

---

### 3.9 SCENE: SETTLEMENT（关卡结算）

| 项 | 内容 |
|----|------|
| 绘制函数 | `FUN_00427f22` |
| 背景 | 无（透明叠加在游戏上） |
| 文字 | `ascii.anm` 逐字符 |
| 起始点 | **(144, 128)** |
| 标题后 | **+32** |
| 行距 | **+16** |

完整计分公式见 `docs/12-ui-layout.md` §2.3。

---

### 3.10 SCENE: REPLAY（录像列表）

| 项 | 内容 |
|----|------|
| 资源 | `ascii.anm` |
| 数据 | `demorpy0/1/2.rpy`（内建演示） |
| 列表项 | 从 `th07.dat` 读出 |

---

### 3.11 SCENE: OPTION（设置）

| 项 | 内容 |
|----|------|
| 资源 | `title01.anm` entry1（复用菜单图集） |
| 选项 | Player / Graphic / BGM / Sound / Mode / SlowMode / Reset / KeyConfig / Quit |

> 设置界面**复用标题界面的文字图集**（同一个 `title01.anm`）。

---

## 4. 全场景资源汇总

| 场景 | 主资源 | 附加资源 |
|------|--------|---------|
| TITLE | title01(32) | front(21) |
| OPTION | title01(32) | — |
| GAME | player(10), etama(11) | eff(17-19), stg*bg*, stg*enm*, ascii(1) |
| DIALOG | std*txt(24) | face_*(25, 28) |
| LOADING | loading(23) | — |
| SETTLEMENT | ascii(1) | — |
| RESULT | result00(42) | ascii(1) |
| SCORE TABLE | ascii(1) | result00(42) |
| MUSIC ROOM | music00(46) | ascii(1), musiccmt.txt |
| STAFF ROLL | staff01(49) | — |
| REPLAY | ascii(1) | — |

---

## 5. 静态布局预览

`tools/ui_preview.py` 生成了 **8 个界面 × 3 种分辨率 = 24 张** 布局样例：

```
work/ui_preview/
  game_480p.png        game_720p.png        game_1080p.png
  settlement_*.png     title_*.png          result_*.png
  scoretable_*.png     music_*.png          staff_*.png
  replay_*.png
```

**这些是几何布局示意，不是截图**：它们按实测常量绘制
（游戏区 384×448、HUD X=512、结算起点 144/128 等），
用于核对比例与缩放行为。

### 5.1 各分辨率的缩放

| 分辨率 | scale | 画布 | 留边 |
|--------|-------|------|------|
| 480p (640×480) | 1.00 | 640×480 | 无 |
| 720p (1280×720) | 1.50 | 960×720 | 左右 160 |
| 1080p (1920×1080) | 2.25 | 1440×1080 | 左右 240 |

### 5.2 生成命令

```powershell
python tools/ui_preview.py                 # 全部界面 × 全部分辨率
python tools/ui_preview.py --screen game   # 只生成一个界面
```

---

## 6. 待完成

- [ ] 场景号（0~12）与上述界面的一一对应（需追踪 `+0x154` 的写入）
- [ ] 每个场景的**完整绘制调用序列**（层序、混合模式）
- [ ] HUD 各标签的精确 Y 坐标
- [ ] 菜单项在屏幕上的坐标（图集已有，绘制点未提取）
- [ ] MUSIC ROOM 的曲目列表布局
- [ ] REPLAY 列表的布局
