# 数学辅助与通用工具（精读）

> 来源：`tools/dump_batch.py` 批量阅读 + 逐个确认。
> 这类函数数量最多（约 590 个未命名小函数），但形态集中，可批量处理。

---

## 1. 曲线与插值

### 1.1 Catmull-Rom 样条（math_catmull_rom）

```c
float math_catmull_rom(float p1, float p2, float p3, float p4, float t)
{
    return ((t - 1.0f) * t * t)                 * p4
         + ((1.0f - t) * (1.0f - t) * t)        * p3
         + ((3.0f - t * 2.0f) * t * t)          * p2
         + ((t * 2.0f + 1.0f) * (t-1) * (t-1))  * p1;
}
```

**这是标准 Catmull-Rom 参数曲线**，用于：
- 敌方移动的平滑路径
- 镜头轨道
- 曲线弹幕轨迹

**重制版可直接照抄**，数学完全标准。

### 1.2 缓动曲线（已有，见 `docs/16`）

ECL 与 ANM 共用 6 种缓动：`t²`、`t³`、`t⁴`、easeOut2/3/4。

---

## 2. 坐标变换

### 2.1 极坐标 → 直角（math_polar_to_xy）

```c
void math_polar_to_xy(float *out, float theta, float radius)
{
    out[0] = cos(theta) * radius;
    out[1] = sin(theta) * radius;
}
```

用于：圆形弹幕生成、追踪子弹方向、环形爆炸。

### 2.2 旋转矩阵

```c
// math_mat_rot_y - 绕 Y 轴
c = cos(a); s = sin(a);
m[0]=c;  m[1]=0; m[2]=-s; m[3]=0;
m[4]=0;  m[5]=1; m[6]=0;  m[7]=0;
m[8]=s;  m[9]=0; m[10]=c; m[11]=0;

// math_mat_rot_z - 绕 Z 轴
c = cos(a); s = sin(a);
m[0]=c;  m[1]=s; m[2]=0; m[3]=0;
m[4]=-s; m[5]=c; m[6]=0; m[7]=0;
```

> **标注**：轴向是从字段布局推断的，未与渲染代码交叉验证。

### 2.3 向量运算

| 函数 | 说明 |
|------|------|
| `math_cross` | 三向量叉积 |
| `math_normalize` | 三向量归一化 |
| `angle_normalize` | 角度归一到 `[-π, π]` |

---

## 3. 数值工具

### 3.1 计数器（counter_inc_capped）

```c
if (*counter < 999999) (*counter)++;
```

**上限 999999** —— 与分数上限 999999999 是不同量级。

### 3.2 值系统（stat_add_capped / stat_raise_max）

```c
// 增加当前值，钳制到上限
void stat_add_capped(obj, int delta) {
    obj->current += delta;
    if (obj->current > obj->max) obj->current = obj->max;
}

// 提升上限，钳制到关卡上限
void stat_raise_max(obj, int delta) {
    obj->max += delta;
    if (obj->max > stage_ceiling) obj->max = stage_ceiling;
}
```

`+0x9618` = 上限，`+0x961c` = 当前值。
值变化时触发 UI 刷新。

### 3.3 时间推进（clock_step_ret）

```c
prev = frame[2];           // 记录上一帧
clock_advance(&frame[2], &frame[1]);   // 推进
return frame[2];
```

---

## 4. 数据结构工具

### 4.1 链表节点（list_node_init / list_node_free）

```c
void *list_node_init(node *n) {
    n->field8  = 0;
    n->field10 = 0;
    n->field2  = 0;
    n->callback = n;        // 自引用
    n->field4 = n->field6 = 0;
    n->flags &= 0xfffe;
    return n;
}

void list_node_free(node *n) {
    if (n->callback) n->callback();
    n->field10 = n->field14 = n->field4 = n->field8 = 0;
    n->callback = 0;
}
```

### 4.2 链表移除（obj_list_remove，见 `docs/15`）

双链表 `+0x10` 前驱 / `+0x14` 后继。

### 4.3 批量重置（obj_reset_batch）

```c
for (i = 0; i < 0x44c; i++) {
    if (record[0x27d]) {
        record[0x27f] = 1;
        record[600]   = 0;
        record[0x25c] = -0.5f;      // 0xbf000000
        record[0x260] = 0;
    }
    record += 0x288;                 // 步长 0x288
}
```

**0x44c 个记录，步长 0x288。**

---

## 5. 系统与 CRT 辅助

| 函数 | 说明 |
|------|------|
| `fpu_set_control` | 保存 FPU 控制字 |
| `lock_leave` | `LeaveCriticalSection`（线程同步） |
| `crt_errno_ptr` | `__getptd()->_terrno` |
| `crt_float_helper_a/b` | CRT 浮点转换 |
| `crt_noop_stub` | 空函数 |
| `__seh_frame` | C++ SEH 序言 |

### 5.1 空函数清单（可直接忽略）

这批函数在发布版被裁剪，**重制版无需实现**：

```
FUN_00418110   空
FUN_0045e4f0   日志（编译掉了）
FUN_00468214   CRT 空函数
```

---

## 6. 渲染入口（render_main_update）

```c
void render_main_update(obj *o) {
    text_render();          // 文字层
    o->field_74bc = 0;
    draw_layer_a();         // 图层 A
    draw_layer_b();         // 图层 B（含视口设置）
    if (o->field_41000)
        anm_draw_center(o + 0x9e50);
}
```

**这是每帧渲染的主入口**，层序为：文字 → 图层 A → 图层 B。

---

## 7. 批量阅读工作流

针对 590 个未命名小函数：

```powershell
# 一次导出 20 个函数体
python tools/dump_batch.py --min-lines 5 --max-lines 20 --count 20

# 或按地址区间
python tools/dump_batch.py --range 401000 402000 --max-lines 15

# 或指定名字
python tools/dump_batch.py --names FUN_00401170,FUN_004012b0

# 按形态分类，先看整体分布
python tools/classify.py
```

**分类统计**（1248 个可分类函数）：

| 类别 | 数量 | 占比 |
|------|------|------|
| other | 802 | 64.3% |
| big (>60 行) | 283 | 22.7% |
| stub（空/常返回） | 123 | 9.9% |
| allocator | 18 | 1.4% |
| dispatch | 10 | 0.8% |
| getter | 10 | 0.8% |
| math_matrix | 2 | 0.2% |

> `other` 占多数说明启发式分类还不够细，
> 但 `stub` 的 123 个可以直接跳过。

---

## 8. 待确认

- [ ] 旋转矩阵的轴向
- [ ] `stat_add_capped` 的语义（生命？分数？）
- [ ] `0x288` 步长的记录是什么对象
- [ ] `render_main_update` 三层的具体内容
