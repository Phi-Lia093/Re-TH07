# `.std` 关卡数据的正式加载器

> 来源：`std_load_stage`（`FUN_00407610`, 42 行）。
>
> **补上了 `.std` 格式从第 10 轮起缺失的运行时部分。**
> 注意：前几轮误以为 `msg` 播放器读 `.std`，那已被否定；
> **这里才是 `stage*.std` 的真正加载器。**

---

## 1. 文件头结构（由加载逻辑确定）

```c
buf = res_load(path, 0);

count_a    = *(short *)(buf + 0);      // +0x00  u16
count_b    = *(short *)(buf + 2);      // +0x02  u16
offset_a   = *(int   *)(buf + 4) + buf;  // +0x04  u32，转绝对
offset_b   = *(int   *)(buf + 8) + buf;  // +0x08  u32，转绝对
obj_table  = buf + 0x490;              // 固定的对象指针表
```

### 1.1 与早期逆向的对照

早期（`docs/10`）从文件字节推出：

```
u16 unknown0, u16 unknown1, u32 offsetA, u32 offsetB
```

现在确认：

| 偏移 | 字段 | 用途 |
|------|------|------|
| `+0x00` | `count_a` | **对象数**（用于分配 `count_a × 0x24c`） |
| `+0x02` | `count_b` | **条目数** |
| `+0x04` | `offset_a` | 区段 A 起点 |
| `+0x08` | `offset_b` | 区段 B 起点 |
| **`+0x490`** | **对象指针表** | `count_a` 个 4 字节相对偏移 |

### 1.2 实测数据对照

```
stage1.std: count_a = 2, count_b = 19, offsetA = 1772, offsetB = 2732
```

- `count_a = 2` → 分配 **2 个** AnmInstance（`2 × 0x24c`）
- `count_b = 19` → 19 个条目
- `0x490 = 1168` → 指针表位置

### 1.3 全 8 关实测（**已验证**）

| 文件 | count_a | count_b | 指针表首项 | 文件大小 |
|------|---------|---------|-----------|---------|
| stage1 | **2** | 19 | 1176 | 3552 |
| stage2 | **8** | 35 | 1200 | 4388 |
| stage3 | **5** | 5 | 1188 | 3836 |
| stage4 | **4** | 10 | 1184 | 5920 |
| stage5 | **8** | 29 | 1200 | 5676 |
| stage6 | **2** | 4 | 1176 | 3144 |
| stage7 | **8** | 30 | 1200 | 5744 |
| stage8 | **8** | 30 | 1200 | 5744 |

**指针表首项恒在 1176–1200 之间**，与 `0x490 = 1168` 起点吻合
（表头之后紧跟数据，偏移约 8–32 字节）。

`count_a` 取值 2–8，全部指针均落在文件范围内 —— **结构完全自洽**。

---

## 2. 内存布局

```c
// 1. 分配对象数组
obj_array = malloc(count_a * 0x24c);      // AnmInstance 数组

// 2. 重定位对象指针表（+0x490 处）
for (i = 0; i < count_a; i++)
    table[i] += buf;                       // 相对 → 绝对

// 3. 重定位 offsetA / offsetB
offset_a = buf + *(u32*)(buf + 4);
offset_b = buf + *(u32*)(buf + 8);
```

### 2.1 `0x490` 这个常量

**对象指针表固定在 `+0x490`（1168 字节）处。**

这意味着文件头是**固定长度**的，而不是变长结构：

```
+0x000  count_a (u16)
+0x002  count_b (u16)
+0x004  offsetA (u32)
+0x008  offsetB (u32)
+0x00C  ...  填充/其他数据 ...
+0x490  对象指针表 [count_a × u32]     ← 相对偏移
        ...  区段 A / 区段 B
```

---

## 3. 与其他系统的关系

| 系统 | 读取者 | 用途 |
|------|--------|------|
| `viewer` | **`std_load_stage`** | 背景对象放置 |
| `viewer` 区段 A | ⬜ 未确认 | 16 字节记录，消费者未知 |
| **区段 B** | **`std_render_section_b`**（`FUN_00407900`） | **3D 背景对象渲染** |

### 3.1 区段 B 的渲染逻辑（已解出）

```c
std_render_section_b(ctx, section_mask)
{
    build_view_projection();              // cam_apply_matrices
    ptr = ctx->offset_b;                  // param_1[299]

    while (*ptr >= 0) {
        entry = ctx->obj_ptrs[*ptr];      // 从 0x490 表取指针
        if (entry->type == section_mask) { // +2 处是类型

            // 计算相对相机的 3D 位置
            pos.x = entry->x + ptr[1] - ctx->camx - ctx->off_x;
            pos.y = entry->y + ptr[2] - ctx->camy - ctx->off_y;
            pos.z = entry->z + ptr[3] - ctx->camz - ctx->off_z;

            // 距离剔除：1300^2 = 1.69e6
            if (dist2 <= 1.69e6) {
                // 点积投影
                depth = pos · view_dir;
                if (depth <= 880.0 && depth >= 60.0) {
                    entry->flags |= 2;    // 标记可见

                    // 绘制子对象
                    for (child = entry->children; child->id >= 0;
                         child = next) {
                        inst = obj_array[child->slot];
                        inst->pos.x = child->x + ptr[1] - camx;
                        ...
                    }
                }
            }
        }
        ptr += *ptr_size;
    }
}
```

### 3.2 关键数值

| 参数 | 值 | 含义 |
|------|-----|------|
| 距离剔除平方 | **1.69e6** | `1300²`，即 1300 单位外不渲染 |
| 近裁剪 | **60.0** | 深度小于 60 不绘制 |
| 远裁剪 | **880.0** | 深度大于 880 不绘制 |
| 类型比较字段 | `+2` | 条目的 section mask |

**这三个值直接决定背景的可见范围，重制版必须照抄。**

> 之前 `msg_run_script` 被误认为 `.std` 播放器，
> 实际它读 `msgN.dat`。**两者完全独立。**

---

## 4. 重制版照抄要点

| 特性 | 建议 |
|------|------|
| `+0x490` 固定指针表位置 | **照抄** |
| 指针表相对 → 绝对重定位 | 照抄（或改写为非破坏性） |
| `count_a × 0x24c` 对象分配 | 照抄（与 AnmInstance 大小一致） |
| 双 count（对象数 + 条目数） | 照抄 |

---

## 5. 待确认

- [ ] `offsetA` / `offsetB` 指向的区段内容与消费者
- [ ] `+0x0C` 到 `+0x48F` 之间的数据（什么用途，为什么这么大）
- [ ] 背景对象（`count_a` 个）的渲染时机
- [ ] `g_stage_std_table` 中各关卡的 `.std` 文件名
