# 道具掉落系统（精读）

> 来源：`item_drop_area_check`（`FUN_004190f0`）与 `item_spawn`（`FUN_00424d20`）、
> `item_spawn_ring`（`FUN_00423730`）。

---

## 1. 掉落触发

`item_drop_area_check` 在敌人死亡时调用，遍历全部敌人槽：

```c
for (i = 0; i < 0x400; i++) {
    e = &enemies[i];                    // 步长 0xd68

    if (e->alive &&
        sprite_height(e) > 48.0 &&      // 只对大体积敌人
        (player->y - 64 < e->y && e->y < player->y + 64)) {   // Y 方向邻近

        for (k = 0; k < item_count; k++) {
            // 在敌人位置 ±16 像素内随机散布
            pos.x = e->x + (rand01() * 32.0 - 16.0);
            pos.y = e->y + (rand01() * 32.0 - 16.0);

            // 随机选择道具类型
            r = rand() & 0xffff;
            switch (r % 3) {
            case 0: kind = 0; sub = 2; break;   // 点数
            case 1: kind = 3; sub = 2; break;   // Bomb
            case 2: kind = 7; sub = 1; break;   // Power
            }

            // 角度：随机 0..270°，或向玩家
            if (mode == 0)
                angle = rand01() * 4.712389 - 1.5707964;   // -90°..180°
            else
                angle = normalize(rand01() * 4.712389 + 0.7853982);

            item.value = 0.01 + rand01() * 0.008;
            item_spawn(&item);
        }

        reset_timer(e);
    }
}
```

### 1.1 掉落数量与难度的关系

```c
switch (difficulty) {
case 0: count = 10;  break;              // Easy
case 1: count = 0x12; break;             // Normal = 18
default: count = 0x19; break;             // Hard/Lunatic = 25
}
```

| 难度 | 每个敌人的掉落数 |
|------|----------------|
| Easy | **10** |
| Normal | **18** |
| Hard / Lunatic / Extra | **25** |

### 1.2 三种道具

| `kind` | `sub` | 推断含义 |
|--------|-------|---------|
| `0` | `2` | **点数道具**（Point item） |
| `3` | `2` | **Bomb 碎片** |
| `7` | `1` | **Power 道具** |

> **标注**：`kind` 到具体道具的对应是**由出现频率和常见设计推断的**，
> 未与贴图资源逐一对照确认。

### 1.3 掉落条件

**只对大体积敌人掉落**：

```c
sprite_height > 48.0
```

小敌人（杂鱼）被击破不掉落，只有中大型敌人掉。
这解释了为什么 TH07 里只有部分敌人掉落道具。

### 1.4 Y 方向窗口

```c
player->y - 64 < enemy->y < player->y + 64
```

**只有敌人死在玩家上下 64 像素范围内才掉落。**

> **标注**：`±64` 窗口是**实测数值**（确证）。
> 至于"这是为了防止刷分"是**设计意图上的推测**，
> 代码本身没有注释说明理由。重制版照抄数值即可，
> 不需要采信这个解释。

---

## 2. 道具生成

### 2.1 item_spawn

```c
void item_spawn(item *it)
{
    if (g_item_count >= 0x400) return;      // 上限 1024

    slot = base + it->kind * 0xb8c;
    value = math_angle_to_target(slot, it->pos);

    for (row = 0; row < it->rows; row++)
        for (col = 0; col < it->cols; col++)
            if (item_spawn_ring(it, col, row, value))
                goto done;

done:
    if (it->flags & 0x200)
        snd_request(it->sound, 0);
}
```

### 2.2 上限

**道具数量上限 `0x400` = 1024**。

### 2.3 弧形布局

`item_spawn_ring` 在 `0x400` 个子弹槽中找空位，
按行列在**以敌人为中心的弧形**上分布道具。

参数 `param_4`（角度）由 `math_angle_to_target` 计算，
使道具**朝玩家方向散开**。

---

## 3. 角度计算（math_angle_to_target）

```c
float math_angle_to_target(obj, point)
{
    if ((obj->y - point->y == 0.0) && (obj->x - point->x == 0.0))
        return PI / 2;                    // 重合时返回 90°

    return atan2(...);
}
```

**重合时返回 π/2** 是为了避免除零。

---

## 4. 重制版照抄要点

### 4.1 关键参数

| 参数 | 值 |
|------|-----|
| 掉落判定 Y 窗口 | ±64 像素 |
| 最小掉落敌人尺寸 | 高度 > 48 |
| 掉落数（Easy/Normal/困难） | 10 / 18 / 25 |
| 散布半径 | ±16 像素 |
| 道具数量上限 | 1024 |

### 4.2 必须保留

| 特性 | 原因 |
|------|------|
| Y 窗口 ±64 | 实测值，影响道具获取 |
| 只掉大敌人 | 影响资源曲线 |
| 难度掉落数 | 直接平衡 |

### 4.3 建议改进

**道具数量上限 1024** 在现代化重制中可以保持，
但如果使用更大的分辨率/更高的敌人密度，需要评估是否上调。

---

## 5. 待确认

- [ ] `kind` 0 / 3 / 7 与贴图的精确对应
- [ ] `item_spawn_ring` 的弧形半径与间距
- [ ] 道具被收集时的效果（点数/Bomb/Power 各加多少）
- [ ] 道具的超时消失机制
