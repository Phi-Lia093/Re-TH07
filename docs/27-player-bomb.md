# 玩家 Bomb 系统与本轮命名修正

> 来源：`player_bomb_step`（`FUN_00441960`）、`player_bomb_spawn_fx`（`FUN_00441bd0`）。
>
> **本文档同时记录一次重要修正**：这两个函数最初被我命名为「死亡序列」，
> 后续追踪发现是 **Bomb 技能**。

---

## 1. 命名修正说明

### 1.1 我最初为什么判断为死亡

- 函数隐藏了玩家两个 sprite（`visible = 0`）
- 生成一个 `0x1c` 类型的特效对象
- 有 4 个阶段的状态机
- 播放两个音效

这些特征确实也符合「死亡」的表现。

### 1.2 推翻判断的证据

1. `+0x2408` 状态字段有**大量函数**写入 `3`，
   其中一处上下文包含 `192.0` 边界、`-π/2` 起始角、
   8 等分和 `anm_set_sprite_script(..., 0x485..)` ——
   这是**灵梦炸弹的符卡环绕弹**，不是死亡。

2. 调用点 `FUN_0042f5a2` 的语义是「值累积到上限时触发」，
   与死亡无关。

3. `+0x2408` 为 1/2 时会**抑制射击计时器**（`FUN_0043d880`），
   符合「Bomb 期间不能射击」。

### 1.3 教训

**同一组视觉特征可以对应多种语义**。「隐藏精灵 + 生成特效 + 多阶段」
在死亡和 Bomb 中都成立。区分必须依赖**状态字段的其他读写点**，
而不是单个函数的表现。

---

## 2. Bomb 状态机

`+0x2408` 字段：

| 值 | 含义 |
|----|------|
| 0 | 空闲 |
| 1 | Bomb 启动 |
| 2 | Bomb 进行中 |
| 3 | Bomb 特效展开 |
| 4 | Bomb 收尾 |

`+0x240d` 是子状态。

### 2.1 流程

```c
void player_bomb_step(player *p)
{
    if (p->invuln_timer != 0 || sys_pause_check()) {
        p->sub_state = 2;
        return;
    }

    switch (p->bomb_stage) {
    case 1:
        if (p->bomb_timer == 0) { p->sub_state = 2; return; }
        player_bomb_spawn_fx(0);
        return;
    case 2:
        if (p->bomb_timer == 0) { p->sub_state = 2; return; }
        break;
    case 3:
        p->sub_state = 2;
        return;
    default:
        // 初始化
        p->bomb_scales[0] = 0x21c;      // 540
        p->bomb_scales[1] = 0;
        p->bomb_scales[2] = -999;
        p->sub_state = 1;
        p->bomb_stage = 4;

        if (p->sprite_a) p->sprite_a->visible = 0;
        if (p->sprite_b) { p->sprite_b->visible = 0; p->sprite_b = 0; }

        fx = obj_spawn_typed(0x1c, &p->pos, 4, 1, -1);
        fx->scale = 0.25f;              // 0x3e800000
        fx->target = 0.25f;
        fx->flip_x = -fx->flip_x;
        p->sprite_c = fx;

        ui_notify_value_change(0, 2);
        snd_request(0x20, 0);
        snd_request(0x24, 0);
        renderer_flags |= 8;
    }
}
```

---

## 3. 两个变体

| 参数 | bomb_step | bomb_spawn_fx |
|------|-----------|---------------|
| 缩放 | `1.0` | `0.25 → 1.3` |
| 时长 | `540` 帧 | `30` 帧 |
| flip | 是 | 否 |

**540 帧（9 秒）**是 Bomb 的持续时间，
**30 帧**是特效爆发的短动画。

---

## 4. 玩家射击计时器（FUN_0043d880）

```c
if (shoot_timer >= 0) {
    if (shoot_timer != prev_shoot_timer && ...) {
        player_fire();                  // FUN_0043d160
    }
    prev_shoot_timer = shoot_timer;
    clock_advance(&shoot_timer, &frac);

    // Bomb 期间或射击过久 → 重置
    if (shoot_timer > 0x1d || bomb_stage == 2 || bomb_stage == 1) {
        shoot_timer = -1;
        frac = 0;
        prev = -999;
    }
}
```

**射击间隔上限 `0x1d` = 29 帧**。
`player_fire`（`FUN_0043d160`）是实际发射函数。

---

## 5. 待确认

- [ ] `player_fire`（`FUN_0043d160`）的完整发射逻辑
- [ ] Bomb 期间的具体无敌时长
- [ ] Bomb 数量扣减的时机
- [ ] `0x16a00..0x16a14` 六个字段的语义
