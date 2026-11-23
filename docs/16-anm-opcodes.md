# ANM 解释器 opcode 语义（从 anm_run_script 精读）

> 来源：`anm_run_script`（`FUN_00450d60`, 1450 行）逐段精读。
> 这是 TH07 的 ANM 字节码解释器，与 ECL 解释器结构高度相似。

---

## 1. 指令格式

```c
struct AnmInstr {          // 以 short 为单位索引
    short opcode;          // psVar1[0]
    short size;            // psVar1[1]  总字节数
    short time;            // psVar1[2]  生效帧
    short param_mask;      // psVar1[3]
    /* 参数，psVar1[4] 开始 */
};
```

**分派方式与 ECL 完全一致**：

```c
switch (*psVar1 + 1) { ... }    // case N 处理 opcode N+1
```

---

## 2. AnmInstance 关键字段

| 偏移 | 含义 |
|------|------|
| `+0x1bb` | 可见/绘制标志（char） |
| `+0x1c6` | 等待计时（short） |
| `+0x1d4` | 当前 sprite 编号 |
| `+0x1e4` | 当前 sprite 结构指针 |
| `+0x1d8` (dword 0x76) | 脚本槽位号 |
| `+0x1dc` (dword 0x77) | **脚本起始指针** |
| `+0x1e0` (dword 0x78) | **当前指令指针** |
| `+0x38` (dword 0xe) | **当前帧计数** |
| `+0x34` (dword 0xd) | 帧小数部分 |
| `+0x30` (dword 0xc) | 帧循环基准（-999 哨兵） |
| `+0x1c0` (dword 0x70) | **标志位**（bit0 运行中, bit3 有缩放, bit7 目标态, bit13 已停止…） |
| `+0x18` (dword 6) | 缩放 X（float） |
| `+0x1c` (dword 7) | 缩放 Y（float） |
| `+0x1b8` (dword 0x6e) | 颜色（ARGB，只有 RGB 部分） |
| `+0x1c8..0x1d0` (dword 0x72..0x74) | 缩放当前值 X/Y/角 |
| `+0x230..0x238` (dword 0x8c..0x8e) | 缩放目标值 X/Y/角 |

---

## 3. 主循环

```c
while (true) {
    // 1. 检查当前帧是否到达
    if (instance->frame_count < instr->time) break;   // 本帧执行完

    // 2. 分派
    switch (instr->opcode + 1) { ... }

    // 3. 前进到下一条（除非指令自己改了指针）
    //    instr += instr->size
}
```

**等待机制**：`+0x1c6` 是等待计数器，非 0 时跳过执行。

---

## 4. 已精读的 opcode

### op 1 (case 0) / op 3 (case 2) / op 4 (case 3) — **结束**

```c
case 0: case 2:
    flags &= ~1;              // 清除"运行中"
case 3:
    ip = NULL;
    return 1;                 // 脚本结束
```

### op 2 (case 1) — **同 case 0**

### op 5 (case 4) — **设置 sprite**

```c
flags |= 1;
sprite_id = (mask & 1) ? read_var(psVar1[4]) : psVar1[4];
anm_bind_sprite(instance, sprite_id + script_slot_base);
instance[0x8f] = instance->frame;      // 记录切换帧
```

> 这是**动画帧切换的核心指令**：`set_sprite`。

### op 6 (case 5) — **无条件跳转**

```c
instance->frame = *(float*)(psVar1 + 6);   // 新时间
instance->frac  = 0;
instance->base  = -999;
instance->ip    = script_start + *(int*)(psVar1 + 4);   // 相对脚本起点
goto dispatch;   // 立即重新分派
```

### op 7 (case 6) — **倒计数跳转**

```c
counter = anm_get_counter(slot, mask, 0);
*counter -= 1;
if (value > 0) {
    frame = *(float*)(psVar1 + 8);
    ip = script_start + *(int*)(psVar1 + 6);
    goto dispatch;
}
```

### op 8 (case 7) — **缩放**

```c
if (!(flags >> 7 & 1)) {
    // 写"当前值"
    instance[0x72] = sx;
    instance[0x73] = sy;
    instance[0x74] = sz;
} else {
    // 写"目标值"
    instance[0x8c] = sx;
    instance[0x8d] = sy;
    instance[0x8e] = sz;
}
// 参数可来自变量：mask bit0/1/2 对应 sx/sy/sz
```

**bit7 决定写当前值还是目标值** —— 这就是 ANM 的**插值机制**：
写入目标值后，渲染时按时间线性逼近。

### op 9 (case 8) — **设置缩放（立即生效）**

```c
instance->scale_x = sx;       // +0x18
instance->scale_y = sy;       // +0x1c
flags |= 8;                   // 标记"有缩放"
```

### op 10 (case 9) — **设置可见性**

```c
*(char*)(instance + 0x1bb) = (char)psVar1[4];
```

### op 11 (case 10) — **设置颜色（RGB）**

```c
instance[0x6e] = (instance[0x6e] & 0xff000000) | (psVar1[4] & 0xffffff);
```

> 只改低 24 位（RGB），保留 alpha。

### op 12 (case 0xb) — **翻转 X**

```c
flags = (flags & ~0x300) | ((flags >> 8 & 3) ^ 1) << 8;
scale_x *= -1.0;
flags |= 8;
```

### op 13 (case 0xc) — **设置位置 Y/Z**

```c
instance[1] = y;      // 位置 Y
instance[2] = z;      // 位置 Z
flags |= 4;           // 标记"有位置"
```

### op 14 (case 0xe) — **设置位置 XYZ**

```c
instance[3] = x;
instance[4] = y;
instance[5] = z;
flags |= 4;
```

### op 15 (case 0xf) — **设置旋转**

```c
instance[8] = angle_x;
instance[9] = angle_y;
// 不设置任何标志位
```

### op 16 (case 0x10) — **设置 alpha（带计时）**

```c
instance[0x22b] = instance[0x1bb];    // 备份可见性
instance[0x22f] = (char)psVar1[4];    // 目标 alpha
instance[0x1a] = 0;                   // 计时清零
instance[0x19] = 0;
instance[0x18] = -999;                // 计时哨兵
instance[0x29] = duration;            // 持续帧数
instance[0x28] = 0;
instance[0x27] = -999;
```

### op 17 (case 0x11) — **设置标志位 bit4**

```c
flags = (flags & ~0x10) | (psVar1[4] & 1) << 4;
```

### op 18/19/20 (case 0x12/0x13/0x14) — **设置插值目标缩放**

```c
// 根据 flags bit7 选择源：
if (!(flags >> 7 & 1)) {
    // 当前值 → 插值起点
    instance[0x7a] = instance[0x72];
    instance[0x7b] = instance[0x73];
    instance[0x7c] = instance[0x74];
} else {
    // 目标值 → 插值起点
    instance[0x7a] = instance[0x8c];
    instance[0x7b] = instance[0x8d];
    instance[0x7c] = instance[0x8e];
}
// 然后读入新目标并启动插值计时
instance[0x7d..0x7f] = 目标值
```

**这三个 opcode 是 ANM 插值动画的核心**：
先把当前缩放存为插值起点，再设置新目标，然后由渲染侧按帧推进。

---

## 5. 字段布局

> **可信度说明**：下表由 opcode 行为反推，
> 位置字段的 XYZ 顺序**未经渲染代码验证**（标记 `?`）。
> 缩放/颜色/标志三组已由多处 opcode 交叉确认。

| dword 下标 | 字节偏移 | 含义 | 可信度 |
|-----------|---------|------|--------|
| `[1]` | `+0x04` | 位置（op13 写的第 1 个） | 推测 |
| `[2]` | `+0x08` | 位置（op13 写的第 2 个） | 推测 |
| `[3]`/`[4]`/`[5]` | `+0x0c` | 位置 XYZ（op14） | 推测 |
| `[6]` | `+0x18` | **缩放 X** | **已确认** |
| `[7]` | `+0x1c` | **缩放 Y** | **已确认** |
| `[8]` | `+0x20` | 旋转 | 推测 |
| `[9]` | `+0x24` | 旋转 | 推测 |
| `[0x6e]` | `+0x1b8` | 颜色 RGB（低 24 位） | **已确认** |
| `[0x70]` | `+0x1c0` | **标志位** | **已确认** |
| `[0x72..0x74]` | `+0x1c8` | 缩放当前 XYZ | **已确认** |
| `[0x7a..0x7c]` | `+0x1e8` | 缩放插值起点 | **已确认** |
| `[0x7d..0x7f]` | `+0x1f4` | 缩放插值终点 | **已确认** |
| `[0x8c..0x8e]` | `+0x230` | 缩放目标 XYZ | **已确认** |
| `[0x1bb]` | | 可见性 | **已确认** |
| `[0x1c6]` | | 等待计数 | **已确认** |

### 标志位 `[0x70]`

| bit | 含义 | 可信度 |
|-----|------|--------|
| 0 | 运行中 | 已确认 |
| 2 | 有位置 | 已确认 |
| 3 | 有缩放 | 已确认 |
| 4 | 未知（op 17 设置） | 待查 |
| 7 | 目标态（写目标值 vs 当前值） | 已确认 |
| 8-9 | X 翻转状态 | 已确认 |
| 13 | 已停止 | 已确认 |

---

## 6. 每帧执行收尾（LAB_004538e2）—— **插值系统核心**

每条指令执行后，解释器都会做一次「每帧更新」：

### 6.1 旋转累加

```c
if (param_2[3] != 0.0)  *param_2   = angle_normalize(*param_2,  g_slow_factor * param_2[3]);
if (param_2[4] != 0.0)  param_2[1] = angle_normalize(param_2[1], g_slow_factor * param_2[4]);
if (param_2[5] != 0.0)  param_2[2] = angle_normalize(param_2[2], g_slow_factor * param_2[5]);
// 同时 flags |= 4
```

`param_2[0..2]` = 旋转角度，`param_2[3..5]` = **角速度**。
`angle_normalize` 把结果归一到 `[-π, π]`。

### 6.2 五组插值器

```c
for (i = 0; i < 5; i++) {
    duration = param_2[i*3 + 0x23];
    if (duration > 0) {
        start = end;                              // 起点 ← 上次终点
        clock_advance(&end, &frac);               // 推进时间
        t = (end + frac) / (duration + start_frac);
        if (current < duration) t = ...; else { t = 1.0; /* 结束，清零计时 */ }
        t = ease(t, param_2[0xc0 + i]);           // 缓动曲线
        value = (target - start) * t + start;
    }
}
```

**五组插值器各自的作用**：

| # | 作用 | 写入字段 | 设置标志 |
|---|------|---------|---------|
| 0 | **缩放** | `[0x72..0x74]`（或目标态 `[0x8c..0x8e]`） | — |
| 1 | **颜色 RGB** | `[0x1ba]`(R) `[0x1b9]`(G) `[0x1b8]`(B) | — |
| 2 | **可见/alpha** | `[0x1bb]` | — |
| 3 | **旋转 XYZ** | `[0]` `[1]` `[2]`（经 angle_normalize） | \|= 4 |
| 4 | **缩放 XY** | `[6]` `[7]` | \|= 8 |

### 6.3 缓动曲线（与 ECL 完全一致）

```c
switch (ease_type) {
    case 1: t = t*t;                          break;   // t²
    case 2: t = t*t*t;                        break;   // t³
    case 3: t = t*t*t*t;                      break;   // t⁴
    case 4: t = 1-(1-t)*(1-t);                break;   // easeOut2
    case 5: t = 1-t; t = 1-t*t*t;             break;   // easeOut3
    case 6: f = (1-t)*(1-t); t = 1-f*f;       break;   // easeOut4
}
```

> 与 ECL 解释器里的缓动公式**逐字相同**（见 `docs/02`），
> 说明 TH07 共用同一套缓动函数。

### 6.4 持续变化量

```c
// 每帧恒定增量（不受插值控制）
param_2[10] += param_2[0x3c];   // 归一化到 [0,1)
param_2[0xb] += param_2[0x3d];

// 帧计数推进
param_2[0xc] = param_2[0xe];
clock_advance(&param_2[0xe], &param_2[0xd]);   // 帧 + 小数
*(int *)(param_1 + 0xc) += 1;                  // 全局帧计数
```

---

## 7. 剩余 opcode（op 22 以后）

| op | case | 语义 |
|----|------|------|
| 22 | 0x15 | **等待**：`+0x1c6 == 0` 时设 bit13 并进入收尾；否则直接收尾 |
| 23 | 0x16 | （缺省，同 op 0） |
| 24 | 0x17 | `flags |= 0xc00`（双轴翻转） |
| 25 | 0x18 | 转 caseD_18（另一等待变体） |
| 26 | 0x19 | 设置 bit7（目标态开关） |
| 27 | 0x1a | `+0x1c4`（short）= 参数（脚本/子 ID） |
| 28 | 0x1b | **角度累加 + 归一化**（`[10]`） |
| 29 | 0x1c | **角度累加 + 归一化**（`[0xb]`） |
| 30 | 0x1d | `flags` bit0 = 参数（启用/暂停） |
| 31 | 0x1e | 设置计时器（`[0x1e..0x20]`） |
| … | 0x1f~0x52 | 未逐个读，结构同前 |

---

## 8. 与 ECL 的对照

| 特性 | ECL | ANM |
|------|-----|-----|
| 分派 | `switch(id - 1)` | `switch(opcode + 1)` |
| 指令头 | 12 字节 | 8 字节 |
| 参数可变 | `param_mask` 位 | 相同 |
| 缓动曲线 | 6 种 | **完全相同** |
| 插值器 | `ins_27` 8 组 | 本例 5 组（固定槽位） |
| 跳转基准 | 相对当前指令 | 相对脚本起点 |

> **重制要点**：两套 VM 共用缓动函数与变量 ID 空间
> （`10000`、`0x2711` 等），说明它们是同一套基础设施的两套前端。
