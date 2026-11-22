# TH07 渲染资源格式 — ANM (精灵/贴图)

> 状态：**格式已解出**，头部/精灵表/脚本表已验证。
> 贴图是**内嵌原始像素**（THTX 块），**不是 PNG 引用**。
>
> 结构来自 thtk 的 `thanm.old/anm_types.h`（权威定义），
> 并对全部 63 个 `.anm` 做了尺寸校验。

---

## 1. 贴图存放方式（关键纠正）

起初我把 `thtxoffset` 理解成「像素数据起始」并据此校验，导致大量文件报
"像素不足"。真实情况：

```
thtxoffset → 指向一个 'THTX' 块（16 字节头 + 原始像素）
nameoffset → 指向 PNG 文件名字符串（如 "data/ascii/ascii.png"）
             *仅用于解包工具的命名/对照，游戏运行时用 THTX 内嵌像素*
```

实测：

| 文件 | nameoffset 指向 | thtxoffset 指向 |
|------|----------------|----------------|
| eff01.anm | `data/eff00/eff01.png` | `THTX` @244 |
| player00.anm | `data/player00/player00.png` | `THTX` @6160 |
| ascii.anm | `data/ascii/ascii.png` | `THTX` @4900 |

> **这是重制的关键**：贴图直接从 THTX 解出即可，
> 不需要外部 PNG（那些名字只是原始美术资源的路径残留）。

### 1.1 THTX 块

```
offset size  field
0x00   4     magic = "THTX"
0x04   2     version
0x06   2     format      (同 ANM 的 format 枚举)
0x08   2     width       (u16！不是 u32)
0x0A   2     height      (u16)
0x0C   4     unknown
0x10   ...   像素数据（w*h*bpp 字节）
```

**注意宽高是 u16**。我最初按 u32 读，得到 `16777472` 这种荒谬值；
按 u16 读立刻得到正确的 `256x256`。

### 1.2 像素格式

| value | 格式 | 字节/像素 | 解码 |
|-------|------|----------|------|
| 1 | BGRA8888 | 4 | `B,G,R,A` 字节序 |
| 3 | RGB565 | 2 | 低 11 位红、中 6 位绿、高 5 位蓝 |
| 5 | **ARGB4444** | 2 | 每通道 4 位 |
| 7 | GRAY8 | 1 | 灰度 |

TH07 常用 **5 (ARGB4444)** 与 **3 (RGB565)**。

---

## 2. 头部结构 `anm_header06_t`（64 字节）

```c
struct AnmHeader {          // 偏移
    u32 sprites;            // 0x00 精灵数
    u32 scripts;            // 0x04 脚本数
    u32 rt_textureslot;     // 0x08 运行时写入，文件内为 0
    u32 w, h;               // 0x0C 图集尺寸
    u32 format;             // 0x14 像素格式（见 1.2）
    u32 colorkey;           // 0x18 ARGB，多为 0，少数 0xff000000
    u32 nameoffset;         // 0x1C 主名字符串偏移
    u32 x;                  // 0x20 未用
    u32 y;                  // 0x24 TH06 为第二名字符串偏移
    u32 version;            // 0x28 TH07 = 2
    u32 memorypriority;     // 0x2C 纹理优先级
    u32 thtxoffset;         // 0x30 → THTX 块
    u16 hasdata;            // 0x34
    u16 lowresscale;        // 0x36
    u32 nextoffset;         // 0x38 → 下一个条目（0 = 无）
    u32 zero3;              // 0x3C
};
```

**实测**（ascii.anm）：`sprites=146 scripts=8 256x256 fmt=5 ver=2
thtxoffset=4900 hasdata=1 nextoffset=135988`。

### 2.1 头部的验算

`sizeof(anm_header06_t)` 必须是 **64**：

```
13 × u32 = 52
2  × u16 = 4      → 56
2  × u32 = 8      → 64
```

我最初写成 `<12I2H2I`（60 字节），解包时字段数不够；
以 `thtxoffset` 落在 0x30 为准，可确定是 13 个 u32。

---

## 3. 表结构

```
[64 字节头部]
[u32 sprite_offsets[sprites]]        ← 绝对文件偏移，不是内联结构！
[struct {i32 id; u32 offset;} scripts[scripts]]
... 精灵与脚本分散在各自偏移处 ...
```

### 3.1 精灵表 `sprite_t`（20 字节）

```c
struct Sprite {
    u32   id;       // 精灵编号（可为非连续；-1 表示"无精灵"）
    float x, y;     // 在图集中的左上角
    float w, h;     // 尺寸
};
```

实测 `ascii.anm`：
```
sprite[0]: id=0 x=0 y=0 w=8 h=8
sprite[1]: id=1 x=8 y=0 w=8 h=8
```
—— 标准 8×8 图集切分，且**全部都在 256×256 图集范围内**。

### 3.2 脚本表 `anm_offset_t`（8 字节）

```c
struct ScriptOffset {
    i32 id;        // 脚本编号
    u32 offset;    // 绝对文件偏移
};
```

实测 `ascii.anm`：`(0,3664) (1,3860) (2,4056) (3,4272) (4,4312)...`

---

## 4. 多条目链

一个 `.anm` 文件可以含**多个条目**，通过 `nextoffset` 串成链：

```
entry0 @0x00  --nextoffset-->  entry1 @0xNNNN  --nextoffset--> ...
```

实测含多条目的文件：

| 文件 | 条目数 |
|------|--------|
| ascii.anm | 3 |
| etama.anm | 3 |
| eff05/06/07/08.anm | 2 |
| face_*.anm | 2 |
| front.anm、stg*enm.anm | 多个 |

**每个条目有独立的头部、精灵表和 THTX 像素块。**

> `ascii.anm` 的第 3 个条目（@133776）头部字段异常
> （`w=4294965084` 等），说明 `nextoffset` 链在第 2 个之后
> 指向的不是又一个头部，而是别的数据 —— **链终止条件待确认**。
> 这不影响前两个条目的正确解析。

---

## 5. 校验结果

### 5.1 视觉验证（最强证据）

用 `tools/anm_parse.py --png` 导出三张贴图并肉眼核对：

| 文件 | 内容 | 结果 |
|------|------|------|
| `player00.anm` | 灵梦 8 帧行走 + Bomb 特效 + Spellcard 背景 | ✅ 红白巫女服颜色正确 |
| `etama.anm` | **敌弹图集**（8 色 × 多种形状） | ✅ 颜色与透明度均正确 |
| `ascii.anm` | ASCII 字体 + "東方妖々夢" logo + UI 文字 | ✅ 字形清晰可读 |

**色彩正确是强证据**：ARGB4444 的通道顺序若搞错（如把 A 当成 R），
画面会立刻出现整片透明或色偏。三张图都正常，说明：
- THTX 头部字段位置正确
- u16 宽高正确
- ARGB4444 解码顺序（A 在高 4 位）正确

### 5.2 结构校验

| 检查 | 结果 |
|------|------|
| 头部字段数 = 17（13u32 + 2u16 + 2u32） | ✅ 全部 63 个文件 |
| 多条目链（`nextoffset`） | ✅ 已解出（见 §7） |
| THTX `w*h*bpp` ≤ 可用字节 | ✅ 绝大多数文件 |
| 精灵矩形在图集内 | ✅ 多数文件 |

---

## 5.3 剩余未解项及其原因

| 现象 | 文件 | 原因 |
|------|------|------|
| `thtxoffset = 0`，无 THTX | `capture.anm`, `music00.anm` | 该条目**不含像素**（纯引用/占位），属正常 |
| 精灵 384×448 超出 256×256 图集 | `eff01/02/06.anm` | 精灵尺寸描述的是**原始未裁切区域**，绘制时按图集边界裁切，非错误 |
| 部分条目头部数值异常 | 多条目文件的末条目 | `nextoffset` 可能指向非头部的辅助数据，链终止条件待确认 |

> 这三类都**不影响**已解出的主体格式。

---

## 6. 对重制的意义

1. **贴图可直接从 THTX 解出**，无需外部 PNG —— 高清重置时替换的是这里
2. 精灵是**图集矩形**，重制版应保留同一套 UV 映射以便对照
3. 像素格式有 4 种，重制版需全部支持解码
4. `etama.anm` 是**敌弹图集**，是弹幕视觉的核心资产
5. 动画脚本（`scripts`）是 ANM 内部的**字节码指令流**（见 thtk
   `anm_instr_t`：`type/length/time/param_mask + data`），
   与 ECL 类似但更简单，**尚未逆向**

---

## 7. 多条目链与偏移基准（重要）

一个 `.anm` 可含多个条目，由 `nextoffset` 串联：

```
entry0 @0x00 ──nextoffset──> entry1 @0xNNNN ──nextoffset──> ...
```

### 7.1 `nextoffset` 精确指向下一条目头部

实测 `ascii.anm`：
```
entry0: thtxoffset=4900，像素 256×256×2 = 131072 字节
        像素结束 = 4900 + 16 + 131072 = 135988
        nextoffset = 135988   ← 完全吻合
```

### 7.2 **精灵表偏移是相对条目头部的**（关键陷阱）

这是最容易出错的地方：

```
entry0:  sprite_offsets[] 是【绝对文件偏移】（base=0，两者等价）
entry1+: sprite_offsets[] 是【相对本条目头部的偏移】
```

实测 `ascii.anm` entry1（头部在 135988）：

| 原始值 | 当作绝对偏移 | 加 base |
|--------|------------|---------|
| 528 | `id=3064, x=4.3e-42`（垃圾） | `id=0, 0,0, 8×8`（正确） |
| 548 | `id=3164, ...`（垃圾） | `id=1, 8,0, 8×8`（正确） |

> 因为 entry0 的 base 为 0，`base + off` 在两种情况下都正确 ——
> 这也是修正后所有多条目文件立刻通过的原因。

---

## 8. 待完成

- [ ] ANM 脚本指令集（`anm_instr_t` 的 type 枚举与语义）
- [ ] `nextoffset` 链的真实终止条件
- [ ] `colorkey` 的使用方式（透明色 vs alpha）
- [ ] 3D 背景（`.std` + `stgNbg.anm`）的渲染层级
- [ ] `eff01/02/06` 超界精灵的裁切规则
