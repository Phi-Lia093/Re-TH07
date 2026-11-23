# 关卡主循环与实体系统（精读）

> 来源：`stage_main_loop`（`FUN_00420620`, 495 行）及配套函数。

---

## 1. 关卡主循环（stage_main_loop）

### 1.1 每帧职责

```c
stage_main_loop(param_1)
    ├── 1. 暂停检查（sys_pause_check）
    ├── 2. 帧计数推进 + 刷怪节奏
    ├── 3. 遍历实体数组，运行 ECL 解释器
    ├── 4. 位置钳制 / 屏幕剔除
    └── 5. 生命周期收尾
```

### 1.2 帧计数与刷怪节奏

```c
if (sys_pause_check() == 0) {
    n = rand();
    if (g_stage_frame != g_stage_frame_prev &&
        g_stage_frame % (n * -0xf0 + 0x960) == 0) {
        snd_play_track(100);         // 每 N 帧触发一次
    }
    g_stage_rate_counter++;
}
```

`n * -0xf0 + 0x960` = `n * -240 + 2400`，即 `2400 - 240n`，
`n` 是随机数 → **每 2400/2160/… 帧触发一次**（动态间隔）。

### 1.3 实体遍历

```c
for (i = 0; i < ecldata->sub_count; i++) {
    if (entity[i].ptr == NULL)
        entity[i].ptr = ecldata->sub_offsets[i];

    ecl_pool_init();
}
```

`g_stage_entities`（`DAT_00954600`）步长 **0x10**，
每项的 `+0` 是延迟初始化的子程序指针。

### 1.4 ECL 执行

```c
local_40 = param_1 + 0x4f50;          // 关卡上下文

if (stage_entity.state >= 0) {         // 未被销毁
    stage_running_count++;

    if (flags->bit3 && (cheat_flags || debug)) {
        clock_skip_frames(1);
        goto end;
    }

    do {
        r = ecl_interpreter(local_40);
        if (r == -1) {
            // 子程序结束 → 释放
            flags &= 0x7f;
            obj_end_lifecycle();
            goto next;
        }
        ...
    } while (...);
}
```

**关键**：`ecl_interpreter` 返回 `-1` 表示该子程序执行完毕。

---

## 2. 屏幕剔除（obj_onscreen_test）

```c
int obj_onscreen_test(float x, float y, float w, float h)
{
    // 注意：这里直接硬编码 384 / 448
    if (x + w/2 < 0.0)      return 0;
    if (x - w/2 > 384.0)    return 0;
    if (y + h/2 < 0.0)      return 0;
    if (y - h/2 > 448.0)    return 0;
    return 1;
}
```

**这是游戏区 `384×448` 的第三次独立确认**（另两次是截图测量、暂停视口设置）。

界面坐标 → 逻辑坐标的关系：

```
屏幕 x = 32 + 逻辑 x
屏幕 y = 16 + 逻辑 y
```

### 2.1 剔除标志

```c
// entity+0x2e29 bit3 = 已剔除（无 sprite）
if (entity->sprite == NULL)
    entity->flags_a |= 8;

// entity+0x2e2a bit3 = 屏幕外
if (!(flags_a bit3) && !(flags_b bit3) && !onscreen(...))
    entity->flags_b |= 8;

// 动画指令推进（仅当在屏幕内）
```

---

## 3. 位置钳制（obj_clamp_position）

```c
void obj_clamp_position(entity *e)
{
    if (e->flags_c & 0x80) {           // 启用钳制
        // X
        if (e->pos_x < e->clamp_x0)      e->pos_x = e->clamp_x0;
        else if (e->pos_x > e->clamp_x1) e->pos_x = e->clamp_x1;
        // Y
        if (e->pos_y < e->clamp_y0)      e->pos_y = e->clamp_y0;
        else if (e->pos_y > e->clamp_y1) e->pos_y = e->clamp_y1;
    }
}
```

| 字段 | 含义 |
|------|------|
| `+0x2e3c` | 钳制 X 最小值 |
| `+0x2e44` | 钳制 X 最大值 |
| `+0x2e40` | 钳制 Y 最小值 |
| `+0x2e48` | 钳制 Y 最大值 |

---

## 4. 实体跟随（sub-entity follow）

当实体有"跟随目标"时，位置**每帧向目标插值 1/16**：

```c
target->x += (entity->x - target->x) * 0.0625;   // 1/16
target->y += (entity->y - target->y) * 0.0625;
target->z += (entity->z - target->z) * 0.0625;
```

**`0.0625 = 1/16`** —— 这是平滑跟随的标准系数，
重制版可照抄。

---

## 5. 轨迹记录

```c
if (entity->trail_enabled) {
    // 向后移位，为新点腾出位置
    for (i = count; i > 1; i--) {
        trail[i] = trail[i - 1];       // 每条记录 0x1c 字节
    }
    trail[0].x0 = entity->x;   trail[0].y0 = entity->y;   trail[0].z0 = entity->z;
    trail[0].x1 = entity->x2;  trail[0].y1 = entity->y2;  trail[0].z1 = entity->z2;
    trail[0].t  = entity->time;
}
```

**0x1c 字节/记录**，用于绘制拖尾效果。

---

## 6. 得分上限

`scene_teardown`（`FUN_0042f45d`）里：

```c
if (g_score_record[1] > 999999999)
    g_score_record[1] = 999999999;
g_score_record[0] = g_score_record[1];
```

**TH07 分数上限 = 999,999,999**。

---

## 7. 暂停触发（game_check_pause）

```c
if (按下暂停键 && 未暂停 && ...) {
    paused = 1;
    g_field_screen_x = 32.0;    // 0x42000000
    g_field_screen_y = 16.0;    // 0x41800000
    g_field_width    = 384.0;   // 0x43c00000
    g_field_height   = 448.0;   // 0x43e00000
    paused_flag = 1;
    if (stage != 6 || time < 300)
        snd_request(6, 0, "Pause");     // 播放暂停音
}
```

**再次确认游戏区 `(32, 16, 384, 448)`。**

---

## 8. 标题界面（ui_title_update）

状态机：`+8` = 状态，`+0xc` = 计时，`+0x64` = 菜单索引。

```c
switch (state) {
case 0:  // 标题主菜单
    if (menu_index==0 || 4 || 7 || 8 || 0xc)
        gfx_load_texture(0, "data/title/title00.jpg");
    break;
case 1:  // 过渡
case 2:  // 退出
    if (timer > 60) { free_resources(); next_scene = -1; }
    break;
case 3:  // 进入子界面
    if (timer > 30) { ... }
    break;
}
```

### 8.1 标题相关图片

| 文件 | 用途 |
|------|------|
| `data/title/title00.jpg` | 标题主背景 |
| `data/title/th07logo.jpg` | Logo |
| `data/title/select00.jpg` | 难度/角色选择背景 |
| `data/title/phantasm.jpg` | Phantasm 专用背景 |

> `select00.jpg` 被**难度选择**和**角色选择**两个界面共用。

---

## 9. 待确认

- [ ] 实体结构完整布局（`+0x2b0c` 起的坐标组）
- [ ] `scene_frame_game`（`FUN_0042e83e`, 280 行）的完整逻辑
- [ ] 轨迹记录的渲染方式
- [ ] 标题状态机 8 个子状态的具体含义
