# Bomb 清屏机制（精读）

> 来源：`player_bomb_clear_start`（`FUN_004411c0`）、
> `player_frame_update`（`FUN_00441330`）、`bullet_clear_all`（`FUN_00424740`）。
>
> 这条链**解答了上上轮遗留的问题**：「死亡/Bomb 时子弹怎么清屏」。

---

## 1. 触发链

```
player_bomb_clear_start (FUN_004411c0)
    │  设置 +0x2400 = 0x3c (60 帧)
    │  缩放玩家精灵（1.0 → 2.0 → 1.0 的脉冲）
    ↓
player_frame_update (FUN_00441330)
    │  每帧: if (+0x2400 != 0) { --+0x2400; bullet_clear_all(0); }
    ↓
bullet_clear_all (FUN_00424740)
       遍历 0x400 个子弹槽（步长 0x35a）
       状态 != 0 且 != 5 的 → 设为 5（消亡）
```

---

## 2. bullet_clear_all 的细节

```c
void bullet_clear_all(obj *root, int kind)
{
    // 1. 清除子弹（0x400 个槽，步长 0x35a）
    for (i = 0; i < 0x400; i++) {
        p = root + i * 0x35a;
        if (p->state != 0 && p->state != 5) {     // 活着
            if (kind == 0 || kind > 8) {
                p->state = 5;                     // 直接消亡
            } else {
                // 转化为"消散"动画
                set_velocity(p, player->speed_table, kind);
                memset(p, 0, 0x35a * 4);
            }
        }
    }

    // 2. 清除另一组对象（0x40 个槽，偏移 +0x366628）
    for (i = 0; i < 0x40; i++) {
        q = root + 0x366628 + i * ...;
        if (q->active && (!(q->flags & 4) || kind == 10)) {
            if (q->state < 2) {
                q->state = 2;
                // 重置计时器
                ...
                // 若是 kind 1..8，让对象向外散开
                for (scale = q->r0; scale < q->r1; scale += 32.0) {
                    sin/cos(angle) ...
                }
            }
        }
    }
}
```

### 2.1 两种清除模式

| `kind` | 行为 |
|--------|------|
| `0` 或 `> 8` | 子弹直接消失（`state = 5`） |
| `1..8` | 子弹转化为**消散动画**（带初速度飞出） |

**Bomb 用的是 `kind = 0`**：直接清场。

### 2.2 状态约定

- `state = 0`：空闲
- `state = 5`：已消亡
- 其他：活跃

---

## 3. 玩家精灵的脉冲缩放

```c
// player_bomb_clear_start
fVar1 = 1.0 - (frame + frac) / 30.0;
player->scale_y = fVar1 * 2.0 + 1.0;     // 3.0 → 1.0
player->scale_x = 1.0 - fVar1 * 1.0;     // 0.0 → 1.0
```

**30 帧内**：
- Y 轴从 `3.0` 缩到 `1.0`
- X 轴从 `0.0` 涨到 `1.0`

这是一个**纵向拉伸后恢复**的脉冲效果，用于 Bomb 释放的视觉冲击。

> 注意 `scale_x` 起点是 `0.0` —— 极窄，
> 视觉上是从一条竖线展开。

---

## 4. 清屏的持续性（关键）

```c
if (bomb_clear_timer != 0) {
    bomb_clear_timer--;
    bullet_clear_all(0);      // 每帧都清
}
```

**60 帧内每帧都清屏**，不是只清一次。

这很重要：单次清屏后新生成的子弹会残留，
而持续清屏保证 Bomb 期间画面上几乎没有子弹。

---

## 5. 其他清屏调用者

`bullet_clear_all` 的调用者：

| 函数 | 用途 |
|------|------|
| `player_frame_update` | Bomb 清屏 |
| `ecl_interpreter` | ECL 的 `ins_` 清屏指令 |
| `bullet_update_all` | 子弹系统内部 |
| `FUN_0040fc90` / `FUN_0041ff80` / `FUN_00429a4f` | 其他场景 |

**ECL 也能触发清屏**，说明关卡脚本可以让全屏子弹消失
（例如 Boss 转换阶段）。

---

## 6. 重制版照抄要点

### 6.1 Bomb 清屏实现

```lua
local BOMB_CLEAR_FRAMES = 60

function player_bomb_start()
    player.bomb_clear_timer = BOMB_CLEAR_FRAMES
    -- 脉冲缩放
    player.scale_anim = { duration = 30, from_y = 3.0, to_y = 1.0,
                          from_x = 0.0, to_x = 1.0 }
end

function player_frame_update()
    if player.bomb_clear_timer > 0 then
        player.bomb_clear_timer = player.bomb_clear_timer - 1
        bullet_clear_all(0)          -- 每帧清
    end
end
```

### 6.2 必须保留

| 特性 | 原因 |
|------|------|
| 60 帧持续清屏 | Bomb 的"安全感"来自持续无弹 |
| 每帧清而非一次清 | 否则新弹会残留 |
| 脉冲缩放 3.0→1.0 / 0.0→1.0 | 视觉冲击 |
| `kind=0` 直接消亡 | Bomb 不做消散动画 |

---

## 7. 待确认

- [ ] `kind = 1..8` 的消散动画各是什么
- [ ] ECL 清屏指令的编号
- [ ] `0x366628` 那组 0x40 个对象是什么
- [ ] Bomb 清屏与无敌（状态 1/2）的时序关系
