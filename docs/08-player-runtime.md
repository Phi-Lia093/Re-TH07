# TH07 玩家运行时逻辑

> 状态：**移动 / 焦点 / 判定 / 相机 已解出并建模验证**
> 射击伤害部分部分解出。
> 全部结论来自 `th07.exe` 反汇编 + `.sht` 数据交叉验证。

---

## 1. 玩家结构体关键字段

由 `FUN_00440cf0`（死亡/复活）与移动函数确定：

| 偏移 | 含义 | 备注 |
|------|------|------|
| `+0x1d8` | 当前 ANM 脚本 ID | `0x400` 待机、`0x401-0x404` 方向 |
| `+0x930` / `+0x934` / `+0x938` | **位置 X / Y / Z** | 与 ECL 变量 `10018/10019` 对应 |
| `+0x948..0x98c` | 碰撞盒四角（3 组） | 见 §4 |
| `+0x990` / `+0x994` | **判定点半宽** | `hitbox / 2` |
| `+0x99c` / `+0x9a0` | **擦弹半宽** | `graze_hitbox / 2` |
| `+0x9cc` / `+0x9d0` | 每帧速度 | |
| `+0x9e8 + n*0x20` | 自机弹幕判定盒（0x70 个） | 激光用 |
| `+0x169fc` / `+0x169f8` | **射击冷却计时** | 上限 `0x1d` = 29 |
| `+0x16a3c..0x16a48` | 射击函数指针（按 `DAT_0062f647` 机体） | |
| `+0x23f0` / `+0x23f4` | 速度**倍率**（非常规 1.0） | |
| `+0x241c` | 输入方向状态 | |
| `+0x2420` / `+0x2424` | 上帧方向 X / Y | 用于动画切换 |
| `+0x2408` | 状态（1=正常, 2=死亡） | |

### 1.1 `.sht` 字段与结构体偏移的对应（已双向验证）

`DAT_00575948` 是已加载的 `.sht` 头指针。反汇编中出现：

```c
*(float *)(player + 0x994) = *(float *)(DAT_00575948 + 0xc)  / 2.0;
*(float *)(player + 0x9a0) = *(float *)(DAT_00575948 + 0x10) / 2.0;
```

而 `.sht` 头部布局为 `u16 u16` + 12 个 float：

| `.sht` 偏移 | 字段 |
|------------|------|
| `0x04` | bombs |
| `0x08` | unknown2 |
| **`0x0c`** | **hitbox** ← 对应 `player+0x994` |
| **`0x10`** | **graze_hitbox** ← 对应 `player+0x9a0` |
| `0x14` | autocollected_item_speed |
| `0x18` | item_hitbox |
| `0x1c` | cherry_loss_on_die |
| `0x20` | point_of_collection |
| **`0x24`** | **hv_speed** |
| **`0x28`** | **hv_focused_speed** |
| **`0x2c`** | **diagonal_speed** |
| **`0x30`** | **diagonal_focused_speed** |

**两份独立数据（反汇编的偏移、`.sht` 的字节布局）完全吻合。**

### 1.2 判定点是半径的一半

引擎把 `.sht` 的 `hitbox` **除以 2** 存放，所以：

```
灵梦:  hitbox 1.65 → 判定半宽 0.825
魔理沙: hitbox 2.20 → 判定半宽 1.100
```

> 玩家看到的小红点是 `hitbox/2` 半径的圆。

---

## 2. 移动逻辑（已完全解出）

### 2.1 8 方向分派（反汇编原文结构）

```c
// 焦点未按下
switch (dir) {
  case 1: local_c = -hv_focused_speed; break;      // 左
  case 2: local_c = +hv_focused_speed; break;      // 右
  ...
}
// 焦点按下（另一套分支）
switch (dir) {
  case 1: local_c = -hv_speed; break;
  ...
}
```

实际上引擎为每个方向组合（含斜向）走不同分支，取字段：

| 输入 | 非焦点 | 焦点 |
|------|--------|------|
| 上下左右 | `hv_speed` | `hv_focused_speed` |
| 斜向（两轴同时） | `diagonal_speed` | `diagonal_focused_speed` |

### 2.2 速度合成与位置更新

```c
player.vx = dir_x * speed_mul_x * slow_factor;
player.vy = dir_y * speed_mul_y * slow_factor;
player.x += player.vx;
player.y += player.vy;
// 然后钳制到 [DAT_0062f874, +DAT_0062f87c] × [DAT_0062f878, +DAT_0062f880]
```

- `slow_factor` = `DAT_00575ac8`（全局慢放系数，正常为 1.0）
- `speed_mul_*` = **`+0x23f0/+0x23f4`，常规下为 1.0**

> **纠错**：我最初把 `0.6`（`0x3f19999a`）当成焦点倍率。
> 实际那是**关卡入场无敌期间**的速度缩放，`1.0` 是恢复正常。
> 焦点模式**不走倍率**，而是直接选 `.sht` 的另一组速度字段。

### 2.3 数值验证

`tools/player_model.py` 对 12 个 `.sht` 校验：

```
file           hitbox    half   graze   ghalf    hv   hvf    diag  diag/hv
ply00a.sht       1.65   0.825    2.80   1.400   4.0  1.60  2.8284  0.70711
ply01a.sht       2.20   1.100    2.50   1.250   5.0  2.00  3.5355  0.70711
ply02a.sht       2.20   1.100    6.00   3.000   4.0  2.20  2.8284  0.70711
```

**全部 12 个文件的 `diag / hv` 精确等于 `1/√2 = 0.70711`。**

这意味着：

```
斜向单轴速度 = 直线速度 / √2
→ 斜向的合速度 |v| = √(2 × (v/√2)²) = v   ← 与直线相同
```

**设计意图得到确认**：斜向移动不会比直线更快。
这是 TH07 手感的基础之一，重制版必须保持。

### 2.4 移动模型

```python
def move(dx, dy, focused, slow_factor=1.0):
    if dx and dy:
        spd = sht.diagonal_focused_speed if focused else sht.diagonal_speed
        sx = sy = spd
    elif dx:
        sx = sht.hv_focused_speed if focused else sht.hv_speed
        sy = 0
    elif dy:
        sy = sht.hv_focused_speed if focused else sht.hv_speed
        sx = 0
    else:
        sx = sy = 0
    pos.x += sx * mul_x * slow_factor
    pos.y += sy * mul_y * slow_factor
    clamp_to_playfield()
```

**实测**（灵梦 A，60 帧 = 1 秒）：
- 按住右：位移 **240.0** = `hv_speed(4.0) × 60` ✓
- 斜向（非焦点）：`|v| = 4.0`（与直线相同）✓
- 斜向（焦点）：`|v| = 1.6`（与直线焦点相同）✓

---

## 3. 方向与动画

```c
// 方向变化时切换 ANM 脚本
if (dir_x < 0)      { anm = 0x401; }
else if (dir_x > 0) { anm = 0x403; }
if (dir_y < 0)      { anm = 0x402; }
else if (dir_y > 0) { anm = 0x404; }
// 都不满足时
if (dir_x == 0 && dir_y == 0) anm = 0x400;  // 待机
```

> 说明：TH07 自机精灵是**左右镜像**的，实际只有左/右两套帧 + 倾斜帧。

---

## 4. 碰撞判定

### 4.1 判定盒构造

```c
// 三组盒子，围绕玩家位置
box0: (x - hw, y - hh, z - hd) .. (x + hw, y + hh, z + hd)
box1: 同样的 ± 擦弹半宽
box2: ± 0x41400000 (12.0)   // 收点盒
```

实测常量：
- `+0x998` = `0x40a00000` = **5.0**（Z 半高）
- `+0x9a4` = 5.0，`+0x9a8` = `0x41400000` = **12.0**

### 4.2 命中测试

```c
if (|bullet.x - player.x| <= player_half + bullet_r &&
    |bullet.y - player.y| <= player_half + bullet_r) return HIT;
```

引擎用的是**轴对齐方框 vs 圆**的近似，而不是精确圆-圆。

- `hitbox` 模式：用 `+0x994`（hitbox/2）
- `graze` 模式：用 `+0x9a0`（graze_hitbox/2）

> 咲夜的 `graze_hitbox = 6.0`（半宽 3.0）远超灵梦的 2.8（半宽 1.4），
> 这就是"咲夜擦弹容易"的量化依据。

---

## 5. 射击系统（部分解出）

### 5.1 冷却计时

```c
FUN_0043d880(player):
    if (player->shot_timer(+0x169fc) >= 0) {
        if (timer != last_timer(+0x169f4)) FUN_0043d160();   // 逐帧发射
        last_timer = timer;
        advance_clock(&timer, &timer_frac);                 // +0x169f8 为小数
        if (timer > 0x1d || state == 2 || state == 1) {      // 29 帧上限
            timer = -1; frac = 0; last = -999;
        }
    }
```

`+0x169fc` 从 0 递增到 **29** 后归 -1（停止）。

**`FUN_0043d160()` 是每帧发射函数**：只要计时值变化就触发一次。

### 5.2 伤害累积

```c
// 激光判定：0x70 个判定盒
for (i = 0; i < 0x70; i++) {
    if (box[i] 与敌弹/敌人重叠) {
        total_damage += box[i].damage;
        box[i].accum += box[i].damage;
    }
}
return total_damage;   // 本帧对敌总伤害
```

### 5.3 激光延伸

```c
// 激光长度按 1/3 计算（可能是"延伸"视觉参数）
pos.x /= 8.0;  pos.y /= 8.0;
```

### 5.4 火力等级

`.sht` 每级 `power` 阈值：`8, 16, 32, 48, 64, 80, 96, 128, 999`

每级是**独立的弹幕表**，所以自机弹幕随火力成长。

### 5.5 未解部分

- [ ] `FUN_0043d160` 内部如何遍历 `.sht` 的射击记录
- [ ] `orb` 字段（0=本体, 1=左子机, 2=右子机）的实际应用
- [ ] `interval` 与冷却计时的关系
- [ ] `homing`（追踪）的实现

---

## 6. 待办

- [ ] 射击发射的具体记录选取逻辑
- [ ] 樱点损失公式（`cherry_loss_on_die` 的实际计算）
- [ ] 死亡 → 复活的无敌帧与位置重置
- [ ] 收点判定（`+0x9a8 = 12.0` 的盒子）
