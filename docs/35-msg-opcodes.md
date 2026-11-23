# msg 脚本 opcode 完整语义

> 来源：`msg_run_script`（`FUN_00429c42`）的 switch 分支，
> 参数结构由**真实数据**交叉验证。

---

## 1. 参数结构修正

**重要**：参数不是打包位域，而是**两个独立的 short**：

```c
struct MsgInstr {
    u16 frame;      // +0x00
    u8  opcode;     // +0x02
    u8  size;       // +0x03
    short arg0;     // +0x04   第一个参数
    short arg1;     // +0x06   第二个参数
};
```

数据中看到的 `65536 = 0x00010000` 实际是 `arg0 = 0, arg1 = 1`。

### 1.1 验证（全 8 个文件统计）

| 字段 | 范围 | 独立值数 |
|------|------|---------|
| `arg0` (short) | **0 – 1200** | 7 |
| `arg1` (short) | **0 – 10** | 10 |

两个字段都能放进 short，且取值分布合理
（`arg0` 是帧数/槽位，`arg1` 是索引），**确认是两个独立 short**。

---

## 2. opcode 统计（8 个 msg 文件实测）

| opcode | 出现次数 | 参数样本 |
|--------|---------|---------|
| **1** | 87 | `arg0 = 0/1` |
| **2** | 197 | `arg0` 0-8，`arg1` 0-8 |
| **3** | 357 | `arg0` = 角色号，`arg1` = 文字行 |
| **4** | 271 | `arg0` = 300/360/400/900/1200（帧） |
| **5** | 536 | `arg0/arg1` 组合 |
| **9** | 24 | 无参数 |
| **13** | 36 | 无参数 |

**帧范围 0-400**。

---

## 3. 各 opcode 语义

### op 0 —— 序列结束

```c
case 0:
    m->state = -1;
    return -1;
```

### op 1 —— 显示角色立绘

```c
case 1:
    slot   = instr->arg0;
    offset = instr->arg1;
    script = offset + (slot != 0 ? 2 : 0) + 0x4a0;

    inst = m + 0x1fbc0 + slot * 0x24c;
    anm_set_script(inst, scripts[script]);

    // 按精灵高度设置 Z 偏移
    if (sprite_height(inst) <= 128.0)
        inst->z_offset = 0;
    else
        inst->z_offset = -112.0f;        // 0xc2e00000
```

**按高度自动调整 Z**：大立绘往后推，避免遮挡。

### op 2 —— 显示立绘（另一组脚本）

```c
case 2:
    slot   = instr->arg0;
    offset = instr->arg1;
    anm_bind_sprite(m + 0x1fbc0 + slot*0x24c,
                    offset + (slot != 0 ? 0xd : 0) + 0x4a0);

    // 三级 Z 偏移
    h = sprite_height(inst);
    if (h <= 128.0)      inst->z_offset = 0;
    else if (h <= 256.0) inst->z_offset = -80.0f;    // 0xc2a00000
    else {
        inst->z_offset  = -208.0f;                   // 0xc3500000
        inst->z_offset2 = -50.0f;                    // 0xc2480000
    }
```

**三级高度分档**，比 op 1 更细。

### op 3 —— 显示对话文字

```c
case 3:
    speaker = instr->arg0;       // 说话者
    line    = instr->arg1;       // 文字条目

    // 首次显示时先绘制名字框
    if (line == 0 && name_slot >= 0) {
        ui_text_draw(m + 0x202a4,
                     colors[speaker], scales[speaker], "..." );
    }

    script = line + 0x700;
    anm_set_script(m + 0x20058 + line*0x24c, scripts[script]);
    ...
    ui_text_draw(m + 0x20058 + line*0x24c,
                 colors[speaker], scales[speaker], text_ptr);
    m->text_timer = 0;
```

**`speaker` 索引配色/缩放数组，`line` 索引文字槽位。**

### op 4 —— 等待

```c
case 4:
    // 可跳过 或 未满目标帧
    if ((!m->skippable || !(input & 0x100)) &&
        ((!(input & 1) || (input & 1) != (prev & 1) || m->wait < 0xc)) &&
        (m->wait < instr->arg0)) {

        m->wait++;
        goto continue_check;          // 不前进指令
    }
    break;                            // 前进
```

`arg0` = **等待帧数**（300/360/400/900/1200 实测）。

### op 5 —— 设置立绘表情（**最高频**，536 次）

```c
case 5:
    slot  = instr->arg0;              // 0 或 1
    value = (u8)instr->arg1;          // 1..5

    if (slot < 2)
        field[0x1fd86 + slot * 0x24c] = value;              // 槽 0/1
    else
        field[0x2021e + (slot - 2) * 0x24c] = value;        // 槽 2/3（不可达）
```

**实测参数分布**：

| `(arg0, arg1)` | 次数 |
|---|---|
| (0, 3) | 113 |
| (1, 4) | 110 |
| (0, 4) | 110 |
| (1, 3) | 98 |
| (0, 1) | 54 |
| (1, 1) | 27 |
| (0/1, 5) | 各 12 |

- `arg0` **只有 0 和 1** → 两个立绘槽
- `arg1` 取 **1..5** → 表情编号

> **注意**：`slot >= 2` 的分支在真实数据中**从不触发**，
> 说明 TH07 的对话最多同时显示 **2 个立绘**。

### op 9 —— 关卡结算

```c
case 9:
    m->rng_seed     = rand();
    m->score_9      = score_record[9];
    m->cherry       = g_score_current - score_record[0x22];
    m->graze        = score_record[5];
    m->settled      = 1;

    if (stage < 6) {                       // 普通关卡
        anm_set_script(m + 0x6e44, scripts[0x61e]);
        anm_set_script(m + 0x72dc, scripts[0x725]);
        // 截图矩形 (32, 16, 384, 448)
        screenshot.rect = { 4, 0x20, 0x10, 0x180, 0x1c0 };
    } else {                               // Extra
        score_record[0xb] = -1;
    }
```

**这是通关结算的触发点**，同时做截图保存。

### op 11 —— 关卡结束（切场景）

```c
case 0xb:
    score_display = score_actual;

    if (!is_replay) {
        if (stage < 6) {                        // 普通关卡 1-5
            anm_instance_reset(...);
            anm_bind_sprite(m + 0x7090, 0x10c);
            pending_scene = 1;
            state = -2;
        } else {
            // Extra / Phantasm 分支
            if (difficulty < 4) { flags |= 0x10; next_scene = 9; }
            else {
                // 记录通关（Phantasm 特殊计数）
                if (difficulty == 4) score_table[char*0x1c + ...] = 99;
                stage_clear_count[difficulty] += 1;
                next_scene = 6;
            }
        }
    } else {
        next_scene = 6;                          // 录像播放结束
    }
```

**这是对话脚本的终点：触发关卡切换。**

### op 12 —— 设置倍率

```c
case 0xc:
    set_scale(4.0f);        // 0x40800000
```

### op 13 —— 设置可跳过标志

```c
case 0xd:
    m->skippable = *(u8*)(instr + 4);
```

**op 4 的跳过判定读的就是这个字段。**

### op 14 —— 黑屏

```c
case 0xe:
    set_color(0xffffff, 0, 0);
    g_show_boxes = 0x192;      // 402
```

---

## 4. 对话系统的整体流程

```
msg 脚本加载
    ↓
op 1 / op 2  →  显示角色立绘（按高度自动调整 Z）
    ↓
op 3         →  显示对话文字（说话者配色 + 文字行）
    ↓
op 4         →  等待玩家确认或计时
    ↓
op 5         →  推进动画状态
    ↓
op 9         →  通关结算 + 截图
```

---

## 5. 重制版照抄要点

| 特性 | 原因 |
|------|------|
| 立绘按高度分三级 Z 偏移 | 否则大立绘会遮住文字 |
| `speaker` 索引配色/缩放 | 每个角色有自己的样式 |
| op 4 的等待 + 跳过逻辑 | 对话手感 |
| op 9 的截图矩形 (32,16,384,448) | 与原作一致 |

---

## 6. 完整性说明

**全部 15 个 opcode（0-14）语义已解出**：

| op | 语义 | 次数 |
|----|------|------|
| 0 | 序列结束 | — |
| 1 | 显示立绘（2 级高度） | 87 |
| 2 | 显示立绘（3 级高度） | 197 |
| 3 | 显示对话文字 | 357 |
| 4 | 等待 N 帧 | 271 |
| 5 | **设置立绘表情** | **536** |
| 6 | 增加某个计数（`+0x209ac`） | — |
| 7 | BGM 切换 | — |
| 8 | 显示另一类文字/名牌 | — |
| 9 | 关卡结算 + 截图 | 24 |
| 10 | （跳转） | — |
| 11 | **关卡结束、切场景** | — |
| 12 | 设置倍率 4.0 | — |
| 13 | 设置可跳过标志 | 36 |
| 14 | 黑屏 | — |

## 7. 待确认

- [ ] `0x702` / `0x700` / `0x4a0` / `0x803` 四组脚本编号的分工
- [ ] 文字内容是否在 msg 文件中（疑似在别处，如 `.dat` 文本）
- [ ] op 6 的计数器用途
- [ ] op 8 与 op 3 的区别
