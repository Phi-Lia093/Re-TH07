# 摄像机关键帧系统（精读）

> 来源：`cam_run_script`（`FUN_00405690`, 381 行）与 `cam_ease_axis`（`FUN_00405370`）。
> **这是 TH07 的第三套字节码虚拟机。**

---

## 1. 三套虚拟机总览

TH07 有三套独立的字节码解释器，结构高度相似：

| 系统 | 入口 | 指令长 | 缓冲 | 用途 |
|------|------|--------|------|------|
| **ECL** | `ecl_interpreter` | 12 字节 | 敌机/关卡脚本 | 弹幕、AI |
| **ANM** | `anm_run_script` | 8 字节 | 精灵动画 | 帧动画、UI |
| **CAM** | `cam_run_script` | **20 字节** | 摄像机轨道 | 关卡运镜 |

**三者共用**：
- 同样的条件跳转/循环语义
- **完全相同的 6 种缓动曲线**
- 相同的时间推进函数 `clock_advance`

---

## 2. 摄像机指令格式

```c
struct CamInstr {        // 20 字节 (0x14)
    int time;            // +0x00  生效帧
    short opcode;        // +0x04
    short pad;           // +0x06
    int p0, p1, p2;      // +0x08, +0x0c, +0x10
};
```

**终止哨兵**：`time == -1`

遍历方式：

```c
for (instr = script; instr->time != -1; instr += 0x14) { ... }
```

---

## 3. 摄像机状态字段

| 偏移 | 含义 |
|------|------|
| `+0x4b0` | 脚本起始指针 |
| `+0x4b4` | 计时哨兵（-999） |
| `+0x4b8` | 帧小数部分 |
| `+0x4bc` | 当前指令的 time |
| `+0x4c0` | 当前指令索引（× 0x14 得偏移） |
| `+0x4cc..0x4d4` | **当前摄像机位置 XYZ** |
| `+0x5298..0x52a0` | 基准位置 XYZ |
| `+0x4dc..0x4e4` | 另一位置组 |
| `+0x4e8..0x4f0` | 插值起点 |
| `+0x500` | 插值时长 |
| `+0x50f4` | 等待/暂停标记 |

---

## 4. 指令语义（已解出的 11 个）

| op | 行为 |
|----|------|
| **0** | 设置基准位置 XYZ，同时写入当前值 |
| **1** | 设置位置组 XYZ（`+0x4dc`） |
| **2** | 把当前值存为插值起点，设置时长，启动插值 |
| **3** | 等待（若 `+0x50f4 == 0` 则推进） |
| **4** | 转到 caseD_4（长分支，含循环/跳转） |
| **5** | 设置 X 轴目标 + 记录起点 |
| **6** | 设置 X 轴插值时长与缓动类型 |
| **7** | 设置 Y 轴目标 + 记录起点 |
| **8** | 设置 Y 轴插值时长 |
| **9** | 设置 Z 轴目标 + 记录起点 |
| **10** | 设置 Z 轴插值时长 |

**XYZ 三轴独立插值**，各有自己的时长和缓动。

---

## 5. 插值执行器（cam_ease_axis）

```c
void cam_ease_axis(obj, axis, cur, start, target, timer, ease)
{
    if (timer->current < timer->duration) {
        // 推进时间
        timer->start = timer->end;
        clock_advance(&timer->end, &timer->frac);

        t = (timer->end + timer->frac) / timer->duration;
    } else {
        // 结束
        timer->end = timer->duration;
        timer->frac = 0;
        timer->start = -999;
        t = 1.0f;
        timer->duration = 0;
    }

    // 缓动曲线
    switch (ease_type) {
    case 1: t = 1.0 - (1-t)*(1-t);              break;   // easeOut2
    case 2: t = 1.0 - t*t*t;                    break;   // easeOut3
    case 3: t = 1.0 - t*t*t*t;                  break;   // easeOut4
    case 4: /* ... */
    }

    // 线性插值
    *cur = (*target - *start) * t + *start;
}
```

### 5.1 与 ANM/ECL 缓动的关系

### 5.1 ANM 的缓动定义（已逐条核对）

```c
case 1: t = t*t;                  // easeIn2
case 2: t = t*t*t;                // easeIn3
case 3: t = t*t*t*t;              // easeIn4
case 4: t = 1-(1-t)*(1-t);        // easeOut2
case 5: t = 1-t; t = 1-t*t*t;     // easeOut3
case 6: f=(1-t)*(1-t); t=1-f*f;   // easeOut4
```

### 5.2 CAM 与 ANM 编号不一致（**移植陷阱**）

| 效果 | ANM case | CAM case |
|------|---------|---------|
| easeIn2 (`t²`) | 1 | — |
| easeIn3 (`t³`) | 2 | — |
| easeIn4 (`t⁴`) | 3 | — |
| **easeOut2 (`1-(1-t)²`)** | **4** | **1** |
| easeOut3 (`1-(1-t)³`) | 5 | 2 |

**同一个编号在不同虚拟机里含义不同。**
重制版若统一缓动表，必须做转换：CAM 的 `case 1` 要映射到统一的
`easeOut2`，绝不能当作 ECL/ANM 的 `case 1`（那是 `t²`，方向相反）。

---

## 6. 摄像机脚本的数据来源

摄像机脚本来自 `ecldata` 中的独立段，与敌机脚本并列。
调用点：

```c
cam_run_script(camera_obj);
```

每帧执行，推进所有轴的插值。

---

## 7. 重制版照抄要点

### 7.1 必须保留

| 特性 | 原因 |
|------|------|
| 20 字节指令格式 | 数据兼容 |
| XYZ 三轴独立插值 | 运镜手感 |
| `-1` 终止哨兵 | 数据格式 |
| 时间推进用 `clock_advance` | 与全局时钟同步 |

### 7.2 可以改进

| 原实现 | 建议 |
|--------|------|
| 三套独立 VM | 统一为一个 VM + 三种指令集 |
| 缓动编号不一致 | 统一编号（但要写转换表） |
| 固定 0x14 指令 | 保留格式，内部用结构体解码 |

### 7.3 关键陷阱

**缓动编号在 CAM 与 ECL 中语义相反**。

若重制版统一缓动表，必须做映射：

```lua
-- CAM case 1 (easeOut2)  →  统一表 ease_out_quad
-- ECL case 1 (easeIn2)   →  统一表 ease_in_quad
```

直接把 CAM 的 `case 1` 当 ECL 的 `case 1` 用，运镜会完全反向。

---

## 8. 待确认

- [ ] case 4（转向/循环）的完整逻辑
- [ ] 摄像机脚本在 ecldata 中的偏移
- [ ] 5 组插值器同时运作的完整列表（代码显示调用 5 次 `cam_ease_axis`）
- [ ] 与 `gfx_build_view` 的对接方式
