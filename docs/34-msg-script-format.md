# 对话消息脚本格式（msg1..8.dat）

> **本文档是对上一轮错误的彻底修正。**
> 上轮我把 `FUN_00429c42` 写成「.std 3D 背景播放器」，
> 后来追到加载函数实际读的是 **`data/msgN.dat`**，已全部改正。

---

## 1. 文件清单

```
data/msg1.dat   3564 B
data/msg2.dat   3948 B
data/msg3.dat   6000 B
data/msg4.dat   7768 B
data/msg5.dat   8880 B
data/msg6.dat  10516 B
data/msg7.dat  13156 B
data/msg8.dat  13024 B
```

**8 个文件，每关卡一个**（对应 stage1..8）。

加载点：

```c
FUN_00429935("data/msg1.dat");   // 关卡 1
FUN_00429935("data/msg2.dat");   // 关卡 2
...
FUN_00429935("data/msg8.dat");   // 关卡 8
```

---

## 2. 文件结构

```
+0x00              u32  entry_count
+0x04              u32  offsets[entry_count]     ← 相对偏移，加载时转为绝对
                   ...
                   [条目数据]
```

### 2.1 加载时的重定位

```c
buf = res_load(path, 0);
count = *(u32*)buf;
for (i = 0; i < count; i++)
    *(u32*)(buf + 4 + i*4) += (int)buf;      // 相对 → 绝对（就地修改）
```

> **注意**：这是**破坏性**修改。同一缓冲区第二次加载会得到错误指针。

### 2.2 实测数据

| 文件 | 大小 | entry_count |
|------|------|------------|
| msg1.dat | 3564 | **22** |
| msg2.dat | 3948 | **22** |
| msg3.dat | 6000 | **22** |
| msg4.dat | 7768 | **22** |
| msg5.dat | 8880 | **23** |
| msg6.dat | 10516 | **23** |
| msg7.dat | 13156 | **23** |
| msg8.dat | 13024 | **23** |

---

## 3. 指令格式（**已实测**）

```c
struct MsgInstr {
    u16 frame;      // +0x00  生效帧
    u8  opcode;     // +0x02
    u8  size;       // +0x03  本指令总字节数
    /* payload，+0x04 开始 */
};
```

### 3.1 实测样本（msg1.dat entry 0）

```
偏移 92:
  00 00 | 01 | 04 | 00 00 00 00
  frame=0  op=1  size=4  arg=0

  00 00 | 02 | 04 | 00 00 00 00
  frame=0  op=2  size=4  arg=0

  00 00 | 05 | 04 | 00 00 01 00
  frame=0  op=5  size=4  arg=0x00010000
```

**每条指令固定 8 字节**（头部 4 + 参数 4），`size` 字段恒为 4。

### 3.2 指令序列（已实测）

每个偏移指向一段**独立的指令序列**，以 `opcode 0` 结束：

| 偏移 | 指令数 | 结束位置 |
|------|-------|---------|
| 92 | **10** | 244 |
| 1124 | **9** | 1264 |
| 1288 | **8** | 1420 |
| 2228 | **9** | 2352 |
| 2376 | **8** | 2528 |
| 3424 | **9** | 3540 |

### 3.3 偏移表有大量重复（关键）

`msg1.dat` 的 22 个偏移中：

```
[92, 1124, 92, 92, 92, 92, 92, 92, 92, 92, 1288, 2228,
 92, 92, 92, 92, 92, 92, 92, 92, 2376, 3424]
```

**`92` 被引用 14 次**，只有 6 个唯一序列。

说明**多个槽位共享同一段动画脚本** —— 与 ECL 的子程序复用是同一思路。
重制版必须支持序列共享，不能为每个引用复制一份。

---

## 4. 执行模型

```c
void msg_run_script(msg *m)
{
    if (m->state < 0) return -1;            // 已结束

    if (m->countdown != 0)
        m->countdown--;

    // 按键快进
    if (m->skippable && (input & 0x100)) {
        m->frame = *(u16*)m->ptr;
        m->frac  = 0;
        m->timer = -999;
    }

    // 主循环：处理所有 frame <= 当前帧 的指令
    while (*(u16*)m->ptr <= m->frame) {
        switch (*(u8*)(m->ptr + 2)) {
        case 0:                             // 结束
            m->state = -1;
            return -1;
        case 1:                             // 绑定 ANM 脚本
            slot = *(short*)(m->ptr + 4);
            off  = *(short*)(m->ptr + 6);
            script = off + (slot != 0 ? 2 : 0) + 0x4a0;
            anm_set_script(m + 0x1fbc0 + slot*0x24c, scripts[script]);
            break;
        case 2: ...
        case 5: ...
        }
        // 前进到下一指令
    }
}
```

### 4.1 opcode 1 —— 绑定动画脚本

```
script_id = *(short*)(ptr + 6) + (slot != 0 ? 2 : 0) + 0x4a0
```

- 槽位 0 → 脚本 `0x4a0 + n`
- 其他槽位 → 脚本 `0x4a2 + n`

**这个 opcode 是对话立绘/文字的动画控制。**

---

## 5. 每帧驱动

```c
void msg_frame_update(msg *m)
{
    if (game_paused) return 1;

    if (m->pending_scene != 0) {
        next_scene = 3;
        m->pending_scene = 0;
    }

    cam_update();
    msg_run_script(m);

    m->frame_counter++;

    // Extra 关卡第 300 帧触发
    if (stage == 6 && m->frame_counter == 300)
        gfx_set_render_mode(0);

    if ((input & 0x100) && g_show_boxes < 8)
        g_show_boxes = 8;

    return 1;
}
```

---

## 6. 与 `.std` 的关系

**无关系。**

上一轮我猜测这个播放器读的是 `stage*.std`，数据直接否定了它：

| 检查 | `stage1.std` 实际 | 结论 |
|------|------------------|------|
| `+0` 处的 u32 | `0x00020002` = 131074 | 不可能是 count |
| `u16[1]` | 19 | 但区段 A 有 59 条记录 |

**`msg*.dat` 与 `stage*.std` 是两种完全独立的文件。**

`.std`（区段 A 的 16 字节记录）的消费者仍未找到。

---

## 7. 重制版照抄要点

| 特性 | 建议 |
|------|------|
| `(frame, opcode, size, arg)` 指令格式 | 照抄 |
| 偏移表重定位 | 改为非破坏性（另存指针数组） |
| opcode 1 的脚本编号公式 | **照抄**（否则动画错位） |
| 按键快进 | 照抄 |
| Extra 第 300 帧触发 | 照抄 |

---

## 8. 待确认

- [ ] opcode 2、3、4、5 的完整语义
- [ ] 条目之间的边界（是否靠 frame 回退或 opcode 0 分隔）
- [ ] `msg*.dat` 中的文本内容位置（是否有明文对话）
- [ ] `.std` 区段 A 的真实消费者
