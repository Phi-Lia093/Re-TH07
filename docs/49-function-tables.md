# 函数指针表清单

> 扫描整个二进制得到的 14 张函数指针表。
> **其中 2 张已完全解出，其余用途未确认。**

---

## 1. 已解出的表

### 1.1 Bomb 表 `0x49D850`（26 项 = 12×2 + 2）

```c
struct BombEntry {           // 8 字节
    void (*update)(void);    // +0x00
    void (*draw)(void);      // +0x04
};
```

| 索引 | 更新 | 绘制 |
|------|------|------|
| 0 | `bomb_00` | `bomb_eff_draw_4layer` |
| 1 | `bomb_01` | `bomb_eff_draw_8x4` |
| 2 | `bomb_02` | `eff_draw_4slots` |
| 3 | `bomb_03` | `eff_draw_3slots` |
| 4 | `bomb_04` | `bomb_eff_draw_8x2_shadow` |
| 5 | `bomb_05` | `bomb_eff_draw_24x3` |
| 6 | `bomb_06` | `eff_draw_3ring` |
| 7 | `bomb_07` | `eff_draw_4orb` |
| 8 | `bomb_08` | `eff_draw_60_offsets` |
| 9 | `bomb_09` | `eff_draw_60_screen` |
| 10 | `bomb_10` | `eff_draw_4slots_offset` |
| 11 | `bomb_11` | `obj_draw_trails` |

详见 `docs/46`、`docs/48`。

### 1.2 插值表 `0x49DFEC`（8 项）

**全部 8 项都是 `ecl_lerp_var`**（ECL 插值函数）。

这说明 ECL 的某种插值指令通过这张表分派，
8 个条目可能对应 **8 种插值曲线**。

> 与 `docs/16` 记录的 5 组插值器（线性/缓入/缓出/缓入出）相关。

---

## 2. 未完全解出的表

| 地址 | 条目 | 首个函数的已知信息 |
|------|------|------------------|
| `0x403940` | 5 | 未命名 |
| `0x40E9D0` | **38** | 未命名 |
| `0x416C38` | **173** | 未命名（**疑为 ECL opcode 表**） |
| `0x4174F8` | 4 | 未命名 |
| `0x4214D8` | 4 | 未命名 |
| `0x436A9C` | 4 | 未命名 |
| `0x45008C` | 4 | 未命名 |
| `0x456CA8` | 9 | 未命名 |
| `0x494448` | 9 | 未命名 |
| `0x49D8B4` | 5 | 未命名 |
| `0x49D8CC` | 5 | 未命名 |
| `0x49DD50` | **26** | 3 项已命名（见下） |

### 2.1 `0x49DD50` 的 26 项（部分已知）

| 索引 | 函数 |
|------|------|
| 0 | `obj_fade_out_60` |
| 1 | `obj_snapshot_and_random` |
| 2 | `obj_copy_player_pos` |
| 4 | `item_drop_variant_e` |
| 5 | `stub_empty_a` |
| 6 | `enemy_find_largest` |
| 7 | `obj_copy_from_player` |
| 8 | `enemy_drop_on_kill` |
| 11 | `obj_setup_with_bgm` |
| **12** | **`slowmo_enter`** |
| **13** | **`slowmo_exit`** |
| 14 | `item_drop_area_check` |
| 15 | `enemy_enter_split` |
| 16 | `item_state_to_homing` |
| 18 | `item_drop_variant_d` |
| 19 | `enemy_burst_8way` |
| 20 | `count_live_type_27c` |
| 22 | `bgm_play_13b` |
| 23 | `item_drop_radius_180` |
| 24 | `item_drop_variant_b` |
| 25 | `item_drop_variant_c` |

**这张表解释了为什么 `slowmo_enter`/`slowmo_exit` 没有直接调用者** ——
它们是被**索引调用**的。

### 2.2 但表本身没有被直接引用（**未解决**）

搜索整个反编译源，**`0x49DD50` 从未被直接引用**。

可能的情况：
- (a) 通过基址 + 索引计算访问（Ghidra 未解析数据引用）
- (b) 与 ECL 的某种"外部调用"指令相关
- (c) 该表未被使用（死数据）

**我没有找到使用它的代码。** 这是一个具体的未解点。

---

## 3. `0x416C38` 是 **ECL opcode 分派表**（**已确证**）

### 3.1 证据

| 检查项 | 结果 |
|--------|------|
| 条目数 | **173** |
| 全部为有效代码地址 | ✅ 173/173 |
| 地址范围 | `0x410741` – `0x417519` |
| 是否落在 `ecl_interpreter` 内 | ✅ **173/173** |
| `ecl_interpreter` | `0x410520`，3349 行 |

**所有 173 个条目都指向 `ecl_interpreter` 内部的代码位置**，
说明它们是该巨型 switch 的 **case 标签地址**。

### 3.2 共享处理逻辑

```
0x412803  被 9 个条目引用
0x413270  被 2 个条目引用
0x41677b  被 2 个条目引用
```

**多个 opcode 共享同一处理代码** ——
这解释了为什么 161 个 opcode 只需要 163 个不同地址。

### 3.3 用途

这张表证明了 ECL 解释器的结构：
**每个 opcode 对应 `ecl_interpreter` 中的一个 case 分支**。

> **注意**：这张表记录的是**编译后的跳转目标**，
> 而不是源码级语义。`docs/03` 的 opcode 语义表仍然是权威来源。
>
> 两者的关系：`docs/03` 说"opcode X 做什么"，
> 这张表说"opcode X 跳到哪个地址"。

### 3.4 重制版是否需要

**不需要这张表。** 重制版应按 `docs/03` 的语义实现 opcode，
而不是复刻编译后的跳转结构。

---

## 4. 重制版的意义

对于重制版，这些表的用途是：

| 表 | 是否需要 |
|----|---------|
| Bomb 表 | ✅ **必须**（决定 12 种 Bomb） |
| 插值表 | ✅ 需要（插值曲线） |
| 其余 | 🔶 取决于是否复用原版脚本 |

**如果重制版加载原版 ECL 脚本，则需要知道 opcode 分派关系**，
但那个关系已经通过 `docs/03` 的 opcode 表确定，不一定需要这张函数表。

---

## 5. 待确认

- [ ] `0x416C38` 是否为 ECL opcode 表（**最高价值**）
- [ ] `0x49DD50` 的访问路径
- [ ] `0x40E9D0`（38 项）的用途
- [ ] 其余 9 张表的用途
