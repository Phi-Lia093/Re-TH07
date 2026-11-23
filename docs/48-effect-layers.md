# 特效绘制层（多子精灵叠加）

> 来源：`bomb_eff_draw_*` 系列函数。
>
> **这是"渲染位置正确、不丢元素"的核心部分。**

---

## 1. 核心模式

所有特效绘制函数都遵循同一模式：

```c
for (每个槽位) {
    if (slot->active) {
        for (每个子层) {
            inst = &slot->instances[sub];
            inst->pos = slot->pos + sub_offset;    // ← 位置 = 槽位位置 + 子层偏移
            inst->pos += SCREEN_OFFSET;            // ← 加屏幕偏移 (32, 16)
            inst->pos.z = 0;                       // ← z 归零
            anm_draw(inst);
        }
    }
}
```

### 1.1 三个必须照抄的点

| 步骤 | 错误后果 |
|------|---------|
| `pos = slot->pos + sub_offset` | 子层堆在一起，看不出层次 |
| `pos += (32, 16)` | **整体偏移 32×16 像素** |
| `pos.z = 0` | 特效被背景遮挡 |

---

## 2. 各 Bomb 的绘制层数

| 绘制函数 | 槽位 | 子层 |
|---------|------|------|
| `bomb_eff_draw_4layer` | 8 | 4 |
| `bomb_eff_draw_8x4` | 8 | 4 |
| `bomb_eff_draw_8x2_shadow` | 8 | **2 + 投影层** |
| `bomb_eff_draw_24x3` | **24** | 3 |

> **已在第 50 轮解出**：这些函数与 Bomb 更新函数在**同一张表**里，
> 每条 8 字节 = `{ 更新函数, 绘制函数 }`。对应关系见 §2.1。

> **注意**：**绘制层数 ≠ 弹幕槽位数**。
> 索引 5 有 24 个弹幕槽，但绘制时每槽 3 层，共 72 个精灵。

---

## 2.1 完整对应表（**已确定**）

Bomb 表位于 `0x49D850`，每条 **8 字节**：

```c
struct BombEntry {
    void (*update)(void);    // +0x00
    void (*draw)(void);      // +0x04
};
```

| 索引 | 更新函数 | 绘制函数 | 绘制结构 |
|------|---------|---------|---------|
| 0 | `bomb_00` | `bomb_eff_draw_4layer` | 8 槽 × 4 层 |
| 1 | `bomb_01` | `bomb_eff_draw_8x4` | 8 槽 × 4 层 |
| 2 | `bomb_02` | `eff_draw_4slots` | 4 槽 |
| 3 | `bomb_03` | `eff_draw_3slots` | 3 槽 |
| 4 | `bomb_04` | `bomb_eff_draw_8x2_shadow` | 8 槽 × 2 层 + 投影 |
| 5 | `bomb_05` | `bomb_eff_draw_24x3` | 24 槽 × 3 层 |
| 6 | `bomb_06` | `eff_draw_3ring` | 3 槽环绕 |
| 7 | `bomb_07` | `eff_draw_4orb` | 4 槽 8 等分 |
| 8 | `bomb_08` | `eff_draw_60_offsets` | 60 槽 |
| 9 | `bomb_09` | `eff_draw_60_screen` | 60 槽 |
| 10 | `bomb_10` | `eff_draw_4slots_offset` | 4 槽 |
| 11 | `bomb_11` | `obj_draw_trails` | 拖尾 |

### 2.2 修正了两个早期的错误命名

早期我根据函数体形态把这两个命名为
`player_shot_spread`（玩家散射弹）和 `player_orb_draw`（环绕弹）。

**查表后发现它们其实是 Bomb 的绘制函数。**

重读函数体确认：
- `FUN_0040bca0`：**3 个槽位**围绕玩家做**随机角度环形偏移**
- `FUN_0040c160`：**4 个槽位**在 `-π` 起按 `π/5` 间隔分布

两者都是**Bomb 特效**，不是玩家射击。

**已改名为 `eff_draw_3ring` 和 `eff_draw_4orb`。**

> **教训**：早期根据"看起来像什么"命名是危险的。
> 只有查了**调用表**才能知道它服务于哪个系统。

## 3. 子层偏移布局

### 3.1 四层版（`bomb_eff_draw_8x4`）

```
子层 0 → 实例 +0x1B8
子层 1 → 实例 +0x404    (+0x24C)
子层 2 → 实例 +0x650    (+0x24C)
子层 3 → 实例 +0x89C    (+0x24C)
```

**每层间隔 `0x24C` = 一个 AnmInstance。**

### 3.2 三层版（`bomb_eff_draw_24x3`）

```
子层 0 → 位置偏移 (slot->pos[0x14], [0x18], [0x1C])
子层 1 → 位置偏移 (slot->pos[0x44], [0x48], [0x4C])
子层 2 → 位置偏移 (slot->pos[0x74], [0x78], [0x7C])
```

**偏移量存储在每个槽位的字段中，不是固定常数。**

### 3.3 带投影层版（`bomb_eff_draw_8x2_shadow`）

```c
// 第一层：正常位置
pos = slot->pos + sub_offset_0;
pos += screen_offset;
pos.z = 0;
scale = 3.2;                        // 0x404ccccd
anm_draw(inst);

// 第二层：沿速度反向投影
pos = slot->pos - vel * 6.0;        // ← 反向偏移 6 倍速度
pos += (-32, -32);                  // ← 额外的固定偏移！
pos.z = 0;
scale = 2.2;                        // 0x400ccccd
anm_draw(inst);
```

**第二层是"速度残影"**，向后方延伸 6 倍速度。

> **关键**：第二层额外加了 `(-32, -32)`，而第一层没有。
> 这个不对称偏移**容易漏掉**，会导致残影位置错误。

---

## 4. 屏幕偏移常量

```c
pos.x += _DAT_0062f864;      // = 32.0
pos.y += _DAT_0062f868;      // = 16.0
```

**对应游戏区原点 `(32, 16)`**（与 `docs/14` 的截图验证一致）。

### 4.1 为什么必须加

特效的坐标是**游戏区局部坐标**（0,0 在游戏区左上角）。
而 D3D 绘制用的是**窗口坐标**。

所以 `窗口 = 局部 + (32, 16)`。

**漏掉这一步，整个特效会向左上偏移 32×16 像素。**

---

## 5. 场景投影设置（`gfx_setup_scene_projection`）

```c
void gfx_setup_scene_projection(void)
{
    half_w = screen.width / 2.0;
    half_h = screen.height / 2.0;
    aspect = screen.width / screen.height;
    fov    = 0x3ea0d97c;              // π/10 = 18°

    dist = half_h / tan(fov / 2.0);   // 投影距离

    // 设置视口
    viewport = {half_w, half_h, dist};
    center   = {half_w, half_h, 0};
    up       = {0, -1, 0};            // ← Y 轴向下

    build_view_matrix(...);
    build_projection(fov, aspect, 1.0, 10000.0);
}
```

### 5.1 实测参数

| 参数 | 值 |
|------|-----|
| FOV | **π/10 = 18°**（`0x3ea0d97c`） |
| 近平面 | 1.0 |
| 远平面 | **10000.0**（`0x461c4000`） |
| Y 轴方向 | **向下**（`-1.0`） |

**与 `docs/09` 记录的主投影一致。**

> **注意**：`docs/09` 另外记录了一个 **π/6 的背景相机**。
> 两者不是同一个 —— 场景投影用 π/10，背景用 π/6。

---

## 6. 重制版实现检查表

### 6.1 每个特效绘制前

- [ ] `pos = slot.pos + sub_offset`
- [ ] `pos += (32, 16)`
- [ ] `pos.z = 0`
- [ ] 应用缩放（各层不同：3.2 / 2.2 等）
- [ ] 投影层的额外 `(-32, -32)` 偏移

### 6.2 层数不要搞错

### 6.3 层数是"不丢元素"的检查点

以 `bomb_eff_draw_24x3` 为例：**24 个弹幕槽 × 3 层 = 72 个精灵**。

**如果只画 1 层，视觉上会只剩三分之一。**

同理 `bomb_eff_draw_8x4` 是 8 × 4 = 32 个精灵。

**实现时必须逐层绘制，不能只画主层。**

---

## 7. 待确认

- [ ] `bomb_eff_draw_8x2_shadow` 第二层 `(-32,-32)` 的设计意图
- [ ] **各 Bomb 具体使用哪个绘制函数（函数表未定位）**
- [ ] 缩放系数 3.2 / 2.2 的来源
- [ ] 是否有深度排序
