# .std 3D 背景脚本播放器（精读）

> 来源：`std_run_script`（`FUN_00429c42`, 257 行）、`std_frame_update`（`FUN_00427e7c`）、
> 数据加载函数。
>
> 这补上了之前 `.std` 格式逆向中缺失的**运行时语义**。

---

## 1. 数据加载

```c
void std_load(player)
{
    std_free_data(player);

    buf = res_load(path, 0);              // 从 th07.dat 或磁盘
    if (buf == NULL) {
        dbg_log_append_err("...", arg);
        return -1;
    }

    player->std_data  = buf;
    player->frame     = 0;
    player->entry_ptr = NULL;

    // 把偏移表转成绝对指针（就地修改）
    count = *(int*)buf;                    // +0x00 = 条目数
    for (i = 0; i < count; i++) {
        *(int*)(buf + 4 + i * 4) += (int)buf;   // 相对 → 绝对
    }
}
```

### 1.1 数据头部

| 偏移 | 内容 |
|------|------|
| `+0x00` | 条目数 |
| `+0x04 + i*4` | 第 i 个条目的**相对偏移**（加载时转为绝对） |

> 这与之前从文件直接逆向出的 `.std` 结构一致：
> `u16 unknown, u16 count, u32 offsetA, u32 offsetB`。
> 其中 `+2` 处的 `count` 就是这里的条目数。

---

## 2. 条目结构

每条目的头部：

| 偏移 | 内容 |
|------|------|
| `+0x00` | **生效帧** |
| `+0x02` | **opcode**（1 字节） |
| `+0x04` | **参数** |

### 2.1 opcode 1 —— 生成 3D 对象

```c
case 1:
    slot_index = *(short*)(entry + 4);           // 槽位号
    script_off = *(short*)(entry + 6);           // 脚本偏移
    script_id  = script_off + (slot_index != 0 ? 2 : 0) + 0x4a0;

    instance = player + 0x1fbc0 + slot_index * 0x24c;
    instance->script_id = script_id;
    anm_set_script(instance, anm_mgr->scripts[script_id]);

    // 尺寸小于 128 的对象禁用某项
    if (sprite_height(instance) <= 128.0) {
        instance->field_1fdf0 = 0;
    }
```

**脚本编号 = `0x4a0 + 偏移 + (槽位 != 0 ? 2 : 0)`**

这意味着：
- 槽位 0 用脚本 `0x4a0 + n`
- 其他槽位用脚本 `0x4a2 + n`

---

## 3. 执行模型

```c
void std_run_script(player)
{
    if (player->state < 0) return -1;        // 已结束

    // 1. 递减计时器
    if (player->countdown != 0)
        player->countdown--;

    // 2. 按键可快进
    if (player->can_skip && (input & 0x100)) {
        player->frame = *(u16*)player->entry_ptr;
        player->frac = 0;
        player->timer = -999;
    }

    // 3. 主循环：处理所有生效帧 <= 当前帧的条目
    while (*(u16*)player->entry_ptr <= player->frame) {
        switch (*(u8*)(player->entry_ptr + 2)) {
        case 0:                                    // 结束
            player->state = -1;
            return -1;
        case 1:                                    // 生成 3D 对象
            ...
        case ...:
        }
        // 前进到下一条目
    }
}
```

---

## 4. 每帧驱动

```c
void std_frame_update(player)
{
    if (game_paused) return 1;

    if (player->pending_scene != 0) {
        next_scene = 3;
        player->pending_scene = 0;
    }

    cam_update();
    std_run_script(player);

    player->frame_counter++;

    // Extra 关卡第 300 帧触发
    if (stage == 6 && player->frame_counter == 300)
        gfx_set_render_mode(0);

    // 调试置位
    if ((input & 0x100) && g_show_boxes < 8)
        g_show_boxes = 8;

    return 1;
}
```

**注意**：Extra 关卡（`stage == 6`）在第 300 帧触发一次特殊渲染切换。

---

## 5. 与 `.std` 文件格式的对应（**未确认**）

> **这一节是推测，已被数据否定了一部分，不作为结论。**

之前从文件层逆向（`docs/10`）得到的结构：

```
u16 unknown0, u16 unknown1, u32 offsetA, u32 offsetB
[区段 A: 16 字节记录 × N，0xffffffff 终止]
[区段 B: 指令流]
```

本播放器的加载逻辑（`FUN_00429935`）明确做了：

```c
count = *(int*)buf;                       // 读 +0 处的 int 作为条目数
for (i = 0; i < count; i++)
    *(int*)(buf + 4 + i*4) += (int)buf;   // 偏移表转绝对
```

**但实测数据与之不符**：

```
stage1.std: u16[0]=2  u16[1]=19  offsetA=1772  offsetB=2732  size=3552
            offsetB 处的 u32 = 0     ← 作为 count 不合理
            区段 A 实际有 59 条记录  ← 与 u16[1]=19 不符
```

**结论**：
- 本播放器读的**不是** `stage*.std`（或不是其 `offsetB` 处）
- `+0` 处的 int 在 `stage*.std` 里是 `0x00020002`（u16=`2`,`2`），
  作为 count = 131074 显然错误

**因此**：本播放器加载的是**另一种文件**，与 `stage*.std` 无关。
需要追踪 `FUN_00429935` 的实际调用参数才能确定。

## 6. 重制版照抄要点

### 6.1 必须保留

| 特性 | 原因 |
|------|------|
| 偏移表在加载时转为绝对 | 数据结构约定 |
| 脚本编号 `0x4a0 + offset + (slot?2:0)` | 否则背景对象用错贴图 |
| Extra 第 300 帧触发 | 关卡表现 |
| 按键快进 | 剧情跳过 |

### 6.2 可改进

| 原实现 | 建议 |
|--------|------|
| 就地修改偏移表 | 改为非破坏性解析 |
| 单一播放器实例 | 可支持多背景层并行 |

---

## 7. 待确认

- [ ] opcode 2 及以上的语义（本次只读了 case 0 和 1）
- [ ] 区段 A（16 字节记录）的用途
- [ ] `+0x1fdf0` 字段（尺寸 <= 128 时清零）的含义
- [ ] 槽位号的最大值（`+0x1fbc0 + slot*0x24c`）
