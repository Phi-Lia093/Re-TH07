# 计分系统（精读）

> 来源：`bullet_update_all` 中的命中处理、`score_add_graze`、`score_add_notify`。
>
> **说明**：本文档区分「已确证」与「推断」。
> `case` 分支的数值是实测，但每个分支对应的**游戏内道具名**是推断。

---

## 1. 分数记录结构

`g_score_record`（`DAT_00626278`，200 字节）：

| 偏移 | 含义 | 证据 |
|------|------|------|
| `+0x04` | **当前分数** | ✅ 赋值模式恒为 `value / 10 + 当前值` |
| `+0x18` | **Graze 计数** | 🔶 用于点数道具公式 |
| `+0x1C` | **Graze 上限** | 🔶 同上 |
| `+0x20` | 录像存在标志 | 🔶 |
| `+0x7C` | 显示倍率（`0x43000000` = 128.0） | ✅ |

> **注意分数单位**：分数一律以 `value / 10` 累加，
> 说明**内部单位是 1/10 分**。显示时需要 ×10。

---

## 2. 命中处理分支（bullet_update_all 的 switch）

命中后按**对象类型**分支处理。以下数值为实测：

### 2.1 case 6 —— 点数道具（推断）

```c
if (no_extra_flag == 0) {
    value = (score_record[0x18] / 0x28) * 10 + 300;
    if (value < 1) value = 10;
} else {
    value = 100;
}

ui_popup_small(slot, value, WHITE);
score += value / 10;
```

**公式**：`(graze / 40) * 10 + 300`

即：
- 基础值 **300**
- 每 40 次 Graze 增加 **10**

**这意味着点数道具的价值随 Graze 数增长**，与 TH07 的
「擦弹越多，点数越高」机制吻合。

### 2.2 case 7 —— Power 道具（推断）

```c
if (stage_max <= stage_cur) {
    if (obj->y < sht->collection_line || obj->flag_280) {
        // 在收点线以上（或特殊标志）
        value = 50000;
        color = 0xffffff00;      // 黄色
    } else {
        value = rand() * -100 + 50000;    // 50000 - rand*100
        color = 0xffffffff;      // 白色
    }
    value = value - value % 10;           // 取整到 10
    score += value / 10;
}

// Power 增加
power_value = max_graze * 100 + 1000;
stat_add_graze(power_value);
```

**关键参数**：
- 收点线以上：**固定 50000**（黄色显示）
- 收点线以下：**最多 50000**，随机递减
- **取整到 10**

> `.sht + 0x20` = **`point_of_collection`（收点线）**，值 **128.0**，
> 已在 `docs/06-player-sht.md` 中独立确认。
> 这是 TH07「上线收点」机制的确切实现。

### 2.3 case 8 —— 小 Power（推断）

```c
score_add_graze(0x1e);      // 30
score_add_notify(0x46);     // 70
```

两个独立的加值。

### 2.4 case 9 —— 点数道具变体

```c
value = (score_record[0x18] / 0x28) * 10 + 300;
if (value < 1) value = 10;

if (stage_max <= stage_cur)
    ui_popup_number(slot, value, WHITE);

score += value / 10;

if (stage_max > stage_cur)
    ui_popup_number(slot, 100, 0xffff4040);   // 红色

score_add_graze(100);
```

与 case 6 同公式，但额外有 **Graze +100**。

---

## 3. Graze 计数

```c
void score_add_graze(player, amount)
{
    int prev = player->graze;

    player->graze += amount;
    if (player->graze > player->graze_max)
        player->graze = player->graze_max;

    // 超过某个阈值触发清屏
    if (player->graze_total > stage_max + 50000) {
        player->graze_total = stage_max + 50000;
        player_bomb_step();              // 触发
    }

    if (player->graze达到上限 && 变化)
        ui_notify_value_change(graze - stage_base, 3);
}
```

**Graze 上限 = 关卡最大值 + 50000**。

---

## 4. UI 弹字

```c
ui_popup_number(slot, value, color);
```

在道具位置显示浮动的数字，颜色表示类型：

| 颜色 | 含义 |
|------|------|
| `0xffffffff` | 白（普通） |
| `0xffffff00` | 黄（高价值） |
| `0xffff4040` | 红（特殊） |
| `0xffffc0a0` | 橙（其他） |

---

## 5. 重制版照抄要点

### 5.1 已确证可照抄

| 参数 | 值 |
|------|-----|
| 分数内部单位 | **1/10 分**（显示时 ×10） |
| 点数道具基础值 | **300** |
| 点数道具 Graze 系数 | **每 40 Graze +10** |
| Power 道具上限值 | **50000** |
| Power 价值取整 | **% 10** |
| Graze 上限 | 关卡最大 + **50000** |
| 分数硬上限 | **999,999,999** |

### 5.2 必须保留

| 特性 | 原因 |
|------|------|
| 分数以 1/10 为单位 | 否则数字全错 10 倍 |
| 收点线以上固定 50000 | 上线收点的策略价值 |
| 点数随 Graze 增长 | 核心经济循环 |

### 5.3 注意

`case` 编号（6/7/8/9）是**子弹/道具的视觉类型**，
不是道具种类枚举。重制版不应把 6 硬编码成"点数道具"，
而应通过类型表映射。

---

## 6. 待确认（重要）

| 项 | 状态 |
|----|------|
| case 6/7/8/9 与道具贴图的精确对应 | ⬜ 推断 |
| 死亡时的残机扣除与分数惩罚 | ⬜ 未找到 |
| 樱点（Cherry）的计分方式 | ⬜ 未确认 |
| `+0x18` 是 Graze 还是其他计数 | 🔶 强推断 |
| 各 case 的完整触发条件 | ⬜ 部分 |
