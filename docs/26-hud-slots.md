# HUD 槽位绑定（精读）

> 来源：`hud_setup_slots`（`FUN_00401ba0`）与 `hud_init`（`FUN_00401d70`）。
> 这些函数给出了 HUD 每个元素**用哪个 ANM 脚本**的精确对应。

---

## 1. HUD 初始化

### 1.1 hud_init

```c
void hud_init(hud *h)
{
    // 1. 清零 0x4465 个 dword（整个 HUD 结构）
    for (i = 0; i < 0x4465; i++) *p++ = 0;

    // 2. 加载字体图集（槽位 1）
    if (res_load_anm(1, "data/ascii.anm", 0) != 0) {
        return -1;
    }

    // 3. 加载截屏图集（槽位 4）
    if (res_load_anm(4, "data/capture.anm", 0x724) != 0) {
        return -1;
    }

    // 4. 初始化子结构
    ui_init_sub_a();
    hud_setup_slots();

    return 0;
}
```

**HUD 结构大小：`0x4465` = 17509 dword = 70036 字节（68.4 KB）。**

---

## 2. 槽位绑定（关键数据）

`hud_setup_slots` 精确指定每个 HUD 槽位用哪个脚本：

| 槽位偏移 | 脚本索引 | 参数 | 用途（推断） |
|---------|---------|------|------------|
| `+0x498` | `0x28f00` | 4 | 左上信息块 |
| `+0x6e4` | `0x28efc` | 3 | |
| `+0x930` | `0x28f04` | 5 | |
| `+0xb7c` | `0x28f08` | 6 | |
| `+0xdc8` | `0x28f08` | 6 | 同一脚本复用 |
| `+0x1014` | `0x28f08` | 6 | 同上 |
| `+0x1260` | `0x28f08` | 6 | 同上 |

### 2.1 槽位步长

```
0x498 → 0x6e4  = 0x24c
0x6e4 → 0x930  = 0x24c
0x930 → 0xb7c  = 0x24c
0xb7c → 0xdc8  = 0x24c
0xdc8 → 0x1014 = 0x24c
0x1014 → 0x1260 = 0x24c
```

**每个 AnmInstance 占 `0x24c` 字节**，与前文分析一致。

### 2.2 脚本复用

注意 `0x28f08` 被 **4 个槽位**共用（`+0xb7c`/`+0xdc8`/`+0x1014`/`+0x1260`）。

说明这四个 HUD 元素是**同一种视觉元素**（例如同一图形需要的 4 个实例）。

---

## 3. 脚本编号区间

HUD 使用的脚本索引在 `0x28ef0` 附近：

```
0x28ef0  ← 基址（AnmManager + 0x28ef0）
0x28efc  ← 槽 2 使用
0x28f00  ← 槽 1 使用
0x28f04  ← 槽 3 使用
0x28f08  ← 槽 4/5/6/7 使用
0x28f0c  ← 暂停覆盖层使用
0x28f10  ← ？
```

**索引是 dword 数组下标**，实际指向 AnmManager 内的脚本指针表：

```c
script_ptr = *(u32 *)(anm_mgr + 0x28ef0 + index * 4);
```

### 3.1 与暂停菜单的关系

前面分析过暂停菜单加载脚本 `0xFE..0x107`：

```c
script_id = 0xfe + i;                                    // 0xFE..0x107
anm_set_script(slot, *(u32 *)(mgr + 0x28ef0 + script_id*4));
```

**`0xFE..0x107` 是脚本 ID，而 `0x28ef0 + ID*4` 才是指针地址。**

两者不要混淆：
- `0xFE` = 脚本编号 254
- `0x28ef0 + 254*4 = 0x292E8` = 该脚本指针的位置

---

## 4. 每帧更新链

`game_frame_update`（`FUN_004017e0`）串联了所有子系统：

```c
void game_frame_update(game *g)
{
    // 1. 未暂停：更新粒子
    if (!paused_a && !paused_b) {
        for (i = 0; i < 0x2d3; i++) {          // 723 个粒子
            p = &particles[i];                  // 步长 0x28
            if (p->alive) {
                p->y -= g_slow_factor * 0.5f;   // 下落
                p->t = p->t_end;
                clock_advance(&p->t_end, &p->frac);
                if (p->t_end > 60) p->alive = 0;   // 生命周期 60 帧
            }
        }
    } else if (paused_a) {
        ui_pause_menu(g);
    }

    // 2. 暂停时的另一分支
    if (paused_b) cam_update(g);

    // 3. 推进 7 个 ANM 槽位
    anm_tick_7slots(g);

    // 4. 覆盖层（录制指示等）
    if (flags bit1) {
        if (overlay_slot == 0) {
            overlay_slot = 7;
            anm_set_script(g + 0x9e50, script[0x28f0c]);
        }
        anm_run_script(g + 0x9e50);
    } else {
        overlay_slot = 0;
    }
}
```

### 4.1 粒子系统参数

| 参数 | 值 |
|------|-----|
| 粒子数 | `0x2d3` = 723 |
| 步长 | `0x28` = 40 字节 |
| 生命周期 | 60 帧 |
| 下落速度 | `g_slow_factor * 0.5` |

### 4.2 暂停的双分支

```c
if (!paused_a && !paused_b)  { 正常更新 }
else if (paused_a)           { 暂停菜单 }
if (paused_b)                { 摄像机更新 }
```

**`paused_a` 和 `paused_b` 是两个不同的暂停标志**，控制不同子系统。

---

## 5. 重制版照抄要点

| 数据 | 值 |
|------|-----|
| HUD 结构大小 | `0x4465` dword |
| AnmInstance 步长 | `0x24c` |
| 粒子数 / 步长 | 723 / 40 字节 |
| 粒子生命周期 | 60 帧 |
| HUD 槽位脚本 | 见 §2 表 |

---

## 6. 待确认

- [ ] `0x28ef0` 表中各索引对应的实际脚本内容
- [ ] 4 个槽位复用同一脚本的具体视觉
- [ ] `paused_a` / `paused_b` 的完整语义区别
- [ ] 粒子系统的完整字段布局
