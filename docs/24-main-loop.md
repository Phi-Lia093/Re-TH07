# 主循环与帧调度（精读）

> 来源：`main_loop`（`FUN_00437c70`, 236 行）完整精读。

---

## 1. 每帧执行顺序

```c
main_loop(game)
{
    // 1. 重置渲染状态
    anm_manager[0x2e4d2..0x2e4d3] = 0xff;      // 白色
    anm_manager[0xb933..0xb936]   = 0;         // 清零
    anm_manager[0] = 0x80808080;               // 灰色

    // 2. 输入采样
    input_prev = input_state;
    input_state = input_poll();
    input_repeat = 0;
    if (input_prev == input_state) {
        // 按住重复：每 8 帧触发一次
        if (input_hold > 0x1d) {
            input_repeat = (input_hold % 8 == 0);
            if (input_hold > 0x25) input_hold = 0x1e;
        }
        input_hold++;
    } else {
        input_hold = 0;
    }

    // 3. 场景切换
    if (cur_scene != next_scene) {
        log("scene %d -> %d\n", cur_scene, next_scene);
        ... 大 switch ...
    }

    // 4. 全局帧计数
    cur_scene = next_scene;
    frame_counter++;
    if (frame_counter % 4000 == 3999)
        cmd_check_debug(...);

    return 1;                  // 1 = 正常，4 = 出错
}
```

---

## 2. 输入重复（auto-repeat）

这是**菜单导航的核心机制**：

```c
if (input == input_prev) {
    if (hold > 0x1d) {              // 29 帧后启动重复
        repeat = (hold % 8 == 0);   // 每 8 帧触发一次
        if (hold > 0x25) hold = 0x1e;   // 0x26 → 0x1e，封顶
    }
    hold++;
}
```

### 2.1 参数

| 值 | 含义 |
|----|------|
| `0x1d` (29) | 启动重复的帧数（约 0.5 秒 @60fps） |
| `8` | 重复间隔 |
| `0x1e` (30) | 封顶值 |
| `0x25` (37) | 超过此值则重置 |

### 2.2 重制版实现

```lua
-- 按住方向键约 0.5 秒后开始快速重复
local HOLD_DELAY = 29
local REPEAT_RATE = 8

if cur == prev then
    hold = hold + 1
    if hold > HOLD_DELAY then
        repeat = (hold % REPEAT_RATE == 0)
        if hold > 37 then hold = 30 end
    end
else
    hold = 0
end
```

**这套参数直接决定菜单操作手感，建议照抄。**

---

## 3. 场景状态机

| 当前 | 目标 | 动作 |
|------|------|------|
| 1 | -1 | 退出（return 4） |
| 1 | 2 | `scene_register_game()` |
| 1 | 4 | 转场（return 5） |
| 1 | 5 | `scene_new_result()` |
| 1 | 8 | `scene_new_music()` |
| 1 | 9 | `scene_teardown()` + staff |
| 2 | 7 | → 标题（`scene_new_title`） |
| 2 | 1 | → 游戏 |
| 2 | 3 | `scene_register_game()` |
| 2 | 6 | `scene_new_result()` |
| 8/9 | 1 | → 标题 |
| 9 | 6 | `scene_new_result()` |

切换时会**清空输入状态**：

```c
DAT_004b9e5c = 0;
DAT_004b9e54 = 0;
DAT_004b9e4c = 0;
```

**防止场景切换瞬间的按键被新场景接收。**

---

## 4. 全局帧计数

```c
frame_counter++;                       // +0x150
if (frame_counter % 4000 == 3999)
    cmd_check_debug(&DAT_00497228, arg1, arg2);
```

每 **4000 帧**（约 66 秒 @60fps）触发一次检查。
`cmd_check_debug` 会比较字符串与 `"debug"` 并匹配命令表——
这是**开发者命令通道**，发布版可能无实际作用。

---

## 5. 渲染状态重置

```c
anm_manager[0] = 0x80808080;    // ARGB: 灰
anm_manager[0xb933] = 0;        // 位置
...
```

**每帧开头重置颜色和位置**，说明 ANM 实例状态不是持久的。

---

## 6. MIDI 引擎

TH07 的 BGM 通过 WinMM MIDI 输出：

| 函数 | WinMM 调用 |
|------|-----------|
| `midi_send_long` | `midiOutPrepareHeader` + `midiOutLongMsg` |
| `midi_send_short` | `midiOutShortMsg` |
| `midi_free_buffer` | `midiOutUnprepareHeader` + free |
| `midi_read_vlq` | VLQ 变长整数解码 |

### 6.1 VLQ 解码（可直接照抄）

```c
int midi_read_vlq(byte **p)
{
    int value = 0;
    byte b;
    do {
        b = **p;
        (*p)++;
        value = value * 0x80 + (b & 0x7f);
    } while (b & 0x80);
    return value;
}
```

标准 MIDI 变长整数，用于 delta-time。

### 6.2 缓冲区管理

```c
// 最多 32 个并发 MIDI 头
for (i = 0; i < 0x20; i++) {
    if (headers[i] == target) break;
}
headers[i] = NULL;
midiOutUnprepareHeader(...);
free(header->lpData);
free(header);
```

**32 个 MIDI 缓冲槽位。**

---

## 7. 重制版照抄要点

| 特性 | 建议 |
|------|------|
| 输入重复参数（29/8/30） | **照抄**（手感） |
| 场景切换清空输入 | **照抄**（防误触） |
| 帧计数 `% 4000` | 可改为现代定时器 |
| WinMM MIDI | 替换为内置合成器 |
| 每帧重置 ANM 颜色 | **照抄** |

---

## 8. 待确认

- [ ] `cmd_check_debug` 命令表的完整内容
- [ ] 场景号到界面名称的最终映射（部分已确认）
- [ ] 每帧是否还有其他隐藏的系统调用
