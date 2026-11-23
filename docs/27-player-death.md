# 玩家死亡与重生（精读）

> 来源：`player_die_sequence`（`FUN_00441960`）与 `player_spawn_death_fx`（`FUN_00441bd0`）。

---

## 1. 死亡状态机

`+0x2408` 是死亡阶段：

| 值 | 含义 |
|----|------|
| 1 | 死亡开始 |
| 2 | 死亡中（等待） |
| 3 | 死亡动画 |
| 4 | 重生 |

`+0x240d` 是**子状态**。

---

## 2. 死亡流程

```c
void player_die_sequence(player *p)
{
    // 1. 无敌或暂停 → 不处理
    if (p->invuln_timer != 0 || sys_pause_check()) {
        p->sub_state = 2;
        return;
    }

    switch (p->death_stage) {
    case 1:
        if (p->death_timer == 0) {
            p->sub_state = 2;
            return;
        }
        player_spawn_death_fx(0);
        return;

    case 2:
        if (p->death_timer == 0) { p->sub_state = 2; return; }
        break;

    case 3:
        p->sub_state = 2;
        return;

    default:
        // 2. 初始化死亡
        p->death_scales[0x16a08] = 0x21c;        // 540
        p->death_scales[0x16a04] = 0;
        p->death_scales[0x16a00] = -999;
        p->death_scales[0x16a0c] = p->[0x16a00];
        p->death_scales[0x16a10] = p->[0x16a04];
        p->death_scales[0x16a14] = p->[0x16a08];

        p->sub_state  = 1;
        p->death_stage = 4;

        // 3. 清除玩家精灵
        if (p->sprite_a) p->sprite_a->visible = 0;
        if (p->sprite_b) { p->sprite_b->visible = 0; p->sprite_b = 0; }

        // 4. 生成死亡特效（类型 0x1c）
        fx = obj_spawn_typed(0x1c, &p->pos, 4, 1, -1);
        fx->timer   = -999;
        fx->scale_a = 0x3e800000;      // 0.25
        fx->scale_b = 0x3e800000;      // 0.25
        fx->scale_c = 0x3e800000;      // 0.25
        fx->scale_d = 0x3e800000;      // 0.25
        fx->flip_x  = -fx->flip_x;

        p->sprite_c = fx;

        // 5. 通知与音效
        ui_notify_value_change(0, 2);
        snd_request(0x20, 0);
        snd_request(0x24, 0);
        renderer_flags |= 8;
    }
}
```

---

## 3. 死亡特效参数

| 字段 | 值 | 含义 |
|------|-----|------|
| 类型 | `0x1c` (28) | 死亡爆炸对象 |
| 初始缩放 | `0.25` | `0x3e800000` |
| 目标缩放 | `1.3` | `0x3fa66666` |
| 起始插值 | `0.0625` = 1/16 | `0x3d800000` |
| 时长 | `540` 帧 | `0x21c` |
| 翻转 | X 轴取反 | 镜像 |

### 3.1 两种变体

`player_die_sequence` 和 `player_spawn_death_fx` 是两个相近的版本：

| 参数 | sequence | spawn_fx |
|------|----------|----------|
| 缩放 | `1.0 → 0.25` | `0.25 → 1.3` |
| 时长 | `540` | `30` |
| flip | 是 | 否 |

说明**死亡有拍屏和爆炸两个阶段**。

---

## 4. 重制版照抄要点

### 4.1 必须精确复刻

| 参数 | 后果 |
|------|------|
| 540 帧死亡时长 | 死亡惩罚节奏 |
| 缩放 `0.25 → 1.3` | 爆炸视觉 |
| 两个音效 `0x20`/`0x24` | 死亡音效叠加 |
| 精灵立即隐藏 | 死亡瞬间的表现 |

### 4.2 关于死亡惩罚

**未确认**：我在 `player_die_sequence` 及其附近代码中
**没有找到**清除子弹的调用。

TH07 实际游玩中死亡会清屏，但清除逻辑可能在：
- 调用 `player_die_sequence` 的上层函数
- 或通过某个全局标志间接触发

**这一点不能凭印象补进重制版**，需要继续追踪才能确定。

---

## 5. 待确认

- [ ] 完整的死亡→重生时间线（各阶段帧数）
- [ ] 残机减少的具体时机
- [ ] 重生后的无敌时长
- [ ] 死亡时子弹清除的逻辑位置
- [ ] `0x16a00..0x16a14` 六个字段的完整语义
