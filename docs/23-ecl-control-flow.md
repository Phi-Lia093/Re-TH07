# ECL 控制流语义（精读）

> 来源：`ecl_interpreter` 主分派与跳转实现。
> 补齐 `docs/03` 中缺失的「条件跳转如何影响控制流」部分。

---

## 1. 指令头与 IP 推进

```c
struct EclInstr {          // 以 int 为单位索引
    /* 0 */  ...
    /* [1] */ short opcode;      // 低 16 位
    /* [2] */ ...
    /* [3] */ int  param0;
    /* [4] */ int  param1;
    /* [5] */ int  param/时间;
    /* [6] */ short size;        // 字节长度，位于 +6
    /* [8] */ ...
    /* [10] */ ushort param_mask;
};
```

### 1.1 统一推进

```c
switchD_0041073a_caseD_7e:
    local_c = (int *)((int)local_c + (int)*(short *)((int)local_c + 6));
    goto LAB_0041069a;
```

**所有正常执行的指令**都从这里推进 IP：

```c
ip += *(int16 *)(ip + 6);      // +6 处是 short 类型的 size
```

> 注意 `+6` 是**字节偏移**，读取为 `short`，
> 而 `local_c` 是 `int*`，所以两者混用但结果正确。

---

## 2. 条件跳转的真实语义

条件类指令（op 30-39）的实现形式统一：

```c
case 0x1f:                              // op 32: int 比较 a < b
    a = read_param(1);
    b = read_param(2);
    if (a < b) goto LAB_00411f00;      // ← 条件成立时"跳过"
    break;                              // ← 条件不成立时继续
```

### 2.1 两条路径的汇合

```
条件成立  → LAB_00411f00 → ip += size  （跳过后续，推进到下一条）
条件不成立 → break       → 落入 caseD_7e → ip += size （同样推进）
```

**两条路径都推进 IP。** 所以：

> **ECL 的比较指令是「守卫 / skip」语义，不是传统跳转。**

它检查条件，**条件成立时跳过紧跟在后的指令块**。
真正的跳转由 `ins_2`（jmp）和 `ins_3`（loop）完成。

### 2.2 真实脚本结构（**用数据确认**）

`ecldata4.ecl` sub 47 的实际指令序列：

```
t=0  op38          ← 比较
t=0  op38          ← 比较（可连续）
t=0  op4           ← 赋值
t=0  op2           ← 跳转
t=0  op4
t=0  op2
t=0  op38          ← 比较
t=0  op4
t=0  op2
...
t=0  op4
t=0  op30          ← 比较
t=0  op145         ┐
t=0  op145         ├ 条件块（3 条）
t=0  op145         ┘
t=0  op2           ← 跳转
t=0  op30          ← 比较
t=0  op145 ×3      ← 条件块
t=0  op2
```

**真实模式**：

```
比较指令
   条件块（1~N 条普通指令）
跳转指令
```

**比较成立时跳过整个条件块，直接落到跳转处执行。**

### 2.2.1 条件块长度实测

对 `ecldata4` sub 47 测量「比较 → 到下一个 op2 之间」的长度：

```
条件块长度: [1, 1, 3, 3, 24]
最小 1 条，最大 24 条
```

**块长度不固定**，所以编译器必须知道块在哪结束——
这正是跳转指令紧随块尾的原因：**跳过 = 跳到块末尾后**。

### 2.3 与「条件跳转」的区别

| 模式 | 是否存在于 TH07 |
|------|----------------|
| 比较 → 单条指令 | ✅ 有（短条件块） |
| 比较 → 多条指令 → 跳转 | ✅ **主要模式** |
| 比较 → 直接跟跳转 | ❌ 全局 0 次 |

全局统计（8 文件 / 19919 条指令）显示比较指令后跟的指令：

| 后续 | 次数 |
|------|------|
| `op73` | 72 |
| `op4` | 39 |
| `op13` | 37 |
| `op79` | 27 |
| `op5` | 23 |
| `op2`（跳转） | **0** |

### 2.4 我最初的两处错误

1. **先写成「比较后紧跟 ins_2」** —— 真实数据中此组合 **0 次**。
2. **再写成「守卫单条指令」** —— 遗漏了「比较 → 多条 → 跳转」这个主模式。

两处都是靠统计真实数据发现并修正的。这说明**不能只读解释器就推断脚本用法**。

## 3. 完整条件族

| op | 类型 | 语义 | 成立时 |
|----|------|------|--------|
| 28 | float | `a == b` | 跳过后续块 |
| 29 | int | `a == b` | 跳过 |
| 30 | int | `a != b` | 跳过 |
| 31 | float | `a != b` | 跳过 |
| 32 | int | `a < b` | 跳过 |
| 33 | float | `a < b` | 跳过 |
| 34 | int | `a <= b` | 跳过 |
| 35 | float | `a <= b` | 跳过 |
| 36 | int | `a > b` | 跳过 |
| 37 | float | `a > b` | 跳过 |
| 38 | int | `a >= b` | 跳过 |
| 39 | float | `a >= b` | 跳过 |

**成对出现**：偶数 op 处理 float，奇数（或相邻）处理 int。

---

## 4. 循环与跳转

### 4.1 无条件跳转（`ins_2`）

```c
case 1:                         // op 2
    goto switchD_0041073a_caseD_1;
```

目标计算与 `ins_3` 共享同一段代码。

### 4.2 倒计数循环（`ins_3`）

```c
case 2:                         // op 3
    counter = ecl_addr_var(ip->param_mask_args, 2);
    (*counter)--;

    if ((ip->param_mask & 4) == 0)
        n = ip->param0;
    else
        n = ecl_read_var_i();

    if (n >= 1) goto switchD_0041073a_caseD_1;   // 继续循环
    break;                                        // 退出
```

**先减后判**：`--counter`，然后检查参数是否 `>= 1`。

### 4.3 返回值约定

```c
case 0:                         // op 1
    return 0xffffffff;          // 子程序结束
```

**`ecl_interpreter` 返回 `-1` 表示该子程序执行完毕**，
调用方（`stage_main_loop`）据此释放实体。

---

## 5. 子程序栈（op 42 / caseD_29）

```c
switchD_0041073a_caseD_29:      // op 42 = "Stack Ret"
    if ((flags_b >> 5 & 1) != 0)
        log("error : no Stack Ret\r\n");

    stack_depth--;              // +0x2a7c

    if (stack_frame != 0) {     // +0x8f4
        // 从栈帧恢复 0x1a 个 dword
        memcpy(ctx + 0x6fc, ctx + 0x2ee8, 0x1a * 4);
        ...
    }
```

**调用栈结构**：
- `+0x2a7c` 栈深度
- `+0x8f4` 栈帧指针
- `+0x6fc` / `+0x2ee8` 两组寄存器备份

**TH07 的 ECL 有真实的函数调用栈**，不是简单的跳转。

---

## 6. 参数读取模式

所有指令共享同一套参数读取逻辑：

```c
if ((ip->param_mask & BIT) == 0)
    value = ip->paramN;              // 立即数
else
    value = ecl_read_var_i(ip->paramN);   // 变量间接
```

**位掩码每 1 位对应一个参数**，与 ANM 完全一致。

---

## 7. 重制版照抄要点

### 7.1 必须精确复刻

| 特性 | 后果 |
|------|------|
| **守卫语义（成立时跳过）** | 理解反了会导致所有条件脚本逻辑颠倒 |
| `ip += *(short*)(ip+6)` | 用 int16 读 size，不是 int32 |
| 循环"先减后判" | 差 1 次的循环会导致弹幕模式错位 |
| 返回 `-1` 表示结束 | 实体释放时机 |

### 7.2 建议的实现

```lua
-- 守卫语义的正确实现
local function cond_guard(result)
    if result then
        ip = ip + instr.size    -- 跳过后续
    end
    -- 否继续正常执行
end
```

### 7.3 最容易被误解的一点

**「条件成立 → 跳过后续指令」** 与大多数语言直觉相反。

在重制版代码里建议直接命名为 `skip_if(cond)` 而非 `jump_if`，
避免后续维护者误读。

### 7.4 数据驱动的验证方法

不要只靠阅读代码推断脚本用法。可用的验证脚本：

```python
from ecl_dump import parse
ecl = parse("work/th07_dat/ecldata1.ecl")
# 统计某类指令后面跟什么
import collections
follow = collections.Counter()
for sub in ecl.subs:
    for i in range(len(sub.instrs)-1):
        if 30 <= sub.instrs[i].id <= 39:
            follow[sub.instrs[i+1].id] += 1
print(follow.most_common())
```

本轮正是靠这个方法发现自己对「守卫语义」的用法推断有误。

## 8. 待确认

- [ ] `switchD_0041073a_caseD_1` 的跳转目标计算细节
- [ ] 栈帧完整结构（0x1a 个 dword 的内容）
- [ ] `ins_4` 与 `ins_5` 在守卫语义中的角色
- [ ] 摄像机与 ANM 是否也有守卫语义（推测相同）
