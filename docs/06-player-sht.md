# TH07 玩家系统 (.sht) — 格式已解出

> 状态：**文件格式 100% 校验通过**（12/12 文件）。
> 玩家**运行时逻辑**部分逆向中。
>
> 起点是一份社区文档（用户提供，明确标注"不确定正确性"）。
> 本文档记录**哪些地方它对了、哪里错了**，全部以真实字节为准。

---

## 1. 文档勘误

| 项目 | 文档说法 | 实测 | 结论 |
|------|---------|------|------|
| 射击记录大小 | 按字段累加 = 52 | 52 | ✅ 正确 |
| 终止方式 | "记录的前两个 u16 为 0xffff 则结束" | **4 字节独立标记 `0xFFFFFFFF`** | ❌ **错误** |
| 每关卡结构 | 未说明 | `N × 52 字节记录 + 4 字节终止符` | 补充 |
| `bombs` 为 float | "Why is it a float?" | 实测 3.0，合理 | 无需质疑 |

### 1.1 终止符的错误（关键）

若按文档把终止符当成一条完整 52 字节记录，**每一层都会恰好溢出 52 字节**：

```
ply00a level 0: 记录在 124/176/228，终止符是 4 字节 @280，
                下一层从 284 开始 —— 而不是 280+52=332
```

修正后，9 级全部对齐，且末级末记录 + 终止符 = 文件长度：
```
level8: 2652 → 12 条记录 → 终止符 @3276 → 文件 3280  ✓
```

---

## 2. 文件格式

```c
struct SHTHeader {
    uint16  unknown1;        // 实测恒为 0
    uint16  level_count;     // 12 个文件全部 = 9
    float   bombs;
    float   unknown2;
    float   hitbox;              // 自机判定点半径
    float   graze_hitbox;
    float   autocollected_item_speed;
    float   item_hitbox;
    float   cherry_loss_on_die;
    float   point_of_collection;
    float   hv_speed;            // 横向/纵向移动速度
    float   hv_focused_speed;    // 低速模式
    float   diagonal_speed;      // 斜向移动速度
    float   diagonal_focused_speed;
    struct { uint32 offset; uint32 power; } levels[level_count];
};

struct SHTShot {                 // 52 字节
    uint16 interval;             // 发射间隔（帧）
    uint16 unknown1;
    float  x, y;                 // 相对自机的发射点
    float  hitbox_x, hitbox_y;
    float  angle;                // 弧度
    float  speed;
    uint16 damage;
    uint8  orb;                  // 0 = 本体, 1 = 左子机, 2 = 右子机
    uint8  unknown2;
    uint16 sprite;
    uint16 unknown3;
    uint32 unknown4;             // 文档称"布尔"
    uint32 homing;
    uint32 unknown5;
    uint32 unknown6;
};
// levels[i] 指向 levels[i+1] 之前的一段，由 4 字节 0xFFFFFFFF 终止
```

---

## 3. 校验方法

`tools/sht_parse.py` 对每个文件检查：

1. `size - 52` 是 52 的倍数（含终止符：`(size-52) % 52 == 0` 加上每层 4 字节）
2. 所有层级偏移单调且在文件内
3. 每层以 `0xFFFFFFFF` 终止，且终止符位置 + 4 == 下一层起始
4. 最后一层终止后恰好到达文件尾

**12/12 文件全部通过。**

---

## 4. 实测数值（ply00a = 灵梦 A）

| 字段 | 值 | 解读 |
|------|-----|------|
| bombs | 3.0 | 3 个 BomB |
| hitbox | **1.65** | 判定点半径（TH07 标志性数值） |
| graze_hitbox | 2.8 | 擦弹判定 |
| autocollected_item_speed | 8.0 | 自动收点速度 |
| item_hitbox | 20.0 | 收点判定 |
| cherry_loss_on_die | 0.5 | 死亡时损失 50% 樱点 |
| point_of_collection | 128.0 | 上界收点线 |
| hv_speed | 4.0 | 常速 4 px/帧 |
| hv_focused_speed | 1.6 | 低速 1.6 |
| diagonal_speed | **2.8284** | = 4/√2 = 2.828427 ✓ |
| diagonal_focused_speed | **1.1314** | = 1.6/√2 = 1.131371 ✓ |

> **数值自洽性验证**：斜向速度严格等于直线速度 ÷ √2，
> 这是为了保持斜向移动的**线速度恒定**。两个独立字段同时吻合，
> 说明字段语义与偏移都正确 —— 这比单纯"能解析出来"强得多。

---

## 5. 等级（power）结构

9 个等级，power 阈值：

```
lv0: 8    lv1: 16   lv2: 32   lv3: 48   lv4: 64
lv5: 80   lv6: 96   lv7: 128  lv8: 999(满)
```

每级有独立的发射表（3~12 条记录），所以**自机弹幕随火力成长**。
`lv8` 的 999 是"满火力"哨兵值。

---

## 6. 12 个文件的角色特征（已实测）

```
ply00*  → 灵梦（Reimu）    ply01* → 魔理沙（Marisa）    ply02* → 咲夜（Sakuya）
```

| 自机 | hitbox | graze | hv_speed | hv_focused | diag | bombs |
|------|--------|-------|----------|-----------|------|-------|
| 灵梦 (ply00*) | **1.65** | 2.80 | 4.0 | 1.60 | 2.8284 | 3 |
| 魔理沙 (ply01*) | 2.20 | 2.50 | **5.0** | 2.00 | 3.5355 | 2 |
| 咲夜 (ply02*) | 2.20 | **6.00** | 4.0 | **2.20** | 2.8284 | **4** |

**数值一致性**：三组数据满足 `diag = hv / √2`
（4/√2=2.8284、5/√2=3.5355、4/√2=2.8284），全部精确吻合。

**角色差异与官方设定一致**：
- 灵梦判定点最小（1.65）、速度中等、3 个 Bomb
- 魔理沙移动最快（5.0）但 Bomb 最少（2 个）
- 咲夜擦弹范围最大（6.00）、Bomb 最多（4 个）

### 6.1 `a` / `b` / `s` 后缀的含义

**实测：同一角色的 `a`/`b`/`as`/`bs` 四个文件，头部 12 个浮点常量完全相同。**

```
ply00a / ply00as / ply00b / ply00bs  → hitbox 1.65, hv 4.00, bombs 3（全同）
ply01a / ply01as / ply01b / ply01bs  → hitbox 2.20, hv 5.00, bombs 2（全同）
ply02a / ply02as / ply02b / ply02bs  → hitbox 2.20, hv 4.00, bombs 4（全同）
```

因此可以确定：

- **`a`/`b` = 两种射击类型（Shot Type A / B）**，差异**仅在弹幕表**
- **`s` 后缀不改变移动/判定参数**，只改变弹幕表

> 注：`s` 的确切含义（是否 "slow/focused 时使用的另一套弹幕"）仍需
> 结合运行时逻辑确认。但"不影响移动与判定"这一结论已由数据证实。

---

## 7. 玩家系统逆向（进行中）

已确认的反汇编线索：

### 7.1 玩家结构体字段

`FUN_00440cf0`（死亡/复活逻辑）中：

```c
*(float *)(player + 0x18) = 3.0f;
*(float *)(player + 0x1c) = 3.0f;
*(float *)(player + 0x930) = ...          // 当前 X
*(float *)(player + 0x934) = ...          // 当前 Y
*(undefined2 *)(player + 0x1d8) = 0x400;  // 动画 ID
```

**`+0x18`/`+0x1c` 写入 3.0 而 `.sht` 的 hitbox 是 1.65/2.20**，
两者不等 → `+0x18` 不是判定点本身，可能是碰撞盒或绘制尺寸，**待确认**。

> 注意 `+0x930`/`+0x934` 与 ECL 变量表里的 `10018`(自身 X) / `10019`(自身 Y)
> 完全一致 —— 印证了文档 02 中 10024 用 `FUN_00442370(+0x2b0c)` 计算
> "到玩家角度"的实现基础。

### 7.2 文件加载路径

- `FUN_004395fb`：通用资源加载器（先查 `th07.dat` 封包，再回退磁盘）
- 封包查找：`FUN_0045fab0`，解密：`FUN_0045f960`
- 加载器会输出 `"%s Decode ..."` / `"%s Load ..."` 日志，可作为断点定位依据

### 7.3 `.sht` 常量不在代码中

在 `.text` 段搜索 1.65 / 2.8 的浮点编码 **零命中**，
说明这些数值**只在运行时从文件读取**，不硬编码。
这反证了 `.sht` 确实被程序解析使用（而不是残留数据）。

### 7.4 待完成

- [ ] 定位 `.sht` 加载函数与玩家结构体初始化
- [ ] 射击发射逻辑（`interval`、`orb` 语义）
- [ ] 移动逻辑（`hv_speed` / `diagonal_speed` 的实际应用）
- [ ] 擦弹判定（`graze_hitbox`）
- [ ] 死亡/樱点损失（`cherry_loss_on_die` 的公式）
- [ ] `+0x18` 与 `hitbox` 的关系
