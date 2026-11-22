# ECL 容器格式规范 — 东方妖妖梦 (TH07) `*.ecl`

> 状态：**容器层已完全逆向并经全部 8 个文件 100% 校验通过**。
> 指令层（opcode 语义）见 `docs/02-ecl-instructions.md`（进行中）。

本文所有结论都来自对 `th07.dat` 实际解包数据的逐字节验证，
并与 thtk 的 `thecl/thecl06.c` 交叉印证。

---

## 1. 数据来源

```
th07.dat  --(PBG4/LZSS)-->  ecldata1.ecl ... ecldata8.ecl
```

8 个关卡文件与游戏 Stage 的对应关系：

| 文件 | Stage | subs | timelines |
|------|-------|------|-----------|
| ecldata1.ecl | Stage 1 | 58 | 2 |
| ecldata2.ecl | Stage 2 | 77 | 3 |
| ecldata3.ecl | Stage 3 | 60 | 2 |
| ecldata4.ecl | Stage 4 | 153 | 2 |
| ecldata5.ecl | Stage 5 | 78 | 2 |
| ecldata6.ecl | Stage 6 | 74 | 2 |
| ecldata7.ecl | Extra | 126 | 2 |
| ecldata8.ecl | Phantasm | 136 | 2 |

stage 到文件的映射需在反汇编中确认（`GameManager::RegisterChain` 一类），
当前为约定俗成排序，**标记为待验证**。

---

## 2. 文件头

```
offset  size  type            field
0x00    2     u16             sub_count         子程序数量
0x02    2     u16             timeline_count    该文件中 Timeline 的数量（通常 2~3）
0x04    4*(N) u32             offsets[]         偏移表
```

其中 `N = 16 + sub_count + 1`（TH07 的 `timeline_count_max` 固定为 16）。

**注意**：偏移表长度用的是「最大值 16」而非文件头里的 `timeline_count`。
这是 TH06/TH07 的固定槽位设计：偏移表前 16 项预留给 Timeline，
即使该关卡只有 2 个 timeline，仍有 16 个槽位。

### 偏移表的语义

```
offsets[0 .. 15]              -> Timeline 0..15 的起始偏移（未使用槽位填 0 或无效值）
offsets[16 + s]  for s in 0..sub_count-1
                              -> 子程序 Sub<s> 的起始偏移
offsets[16 + sub_count]       -> 偏移表末尾（= 4 + 4*(16+sub_count+1)）
```

实测（ecldata1.ecl）：`offsets[16] = 300`，而偏移表本身恰好在 0x12C = 300 处结束，
即**第一个子程序紧跟偏移表**。这是关键校验点。

---

## 3. 文件分区

整个文件分为三个连续区块，**无空隙**：

```
[ 头部 + 偏移表 ]  [ Sub 子程序区 ]  [ Timeline 区 ]
0                  offsets[16]      timeline_start ... EOF
```

- `offsets[0..15]` 指向 **Timeline 区**
- `offsets[16+s]` 指向 **Sub 区**的第 s 个子程序
- Sub 区结束后**紧接** Timeline 区（校验：最后一个 Sub 的哨兵末尾
  == `min(非零 offsets[0..15])`）

实测（ecldata1.ecl）：
```
offsets[0..2]   = (35328, 43404, 44920)   <- timeline slots 0,1,2
offsets[16]     = 300                      <- 紧跟偏移表
offsets[16+57]  = 34756                    <- 最后一个 sub
last sub sentinel @35316, ends @35328      <- 与 timeline_start 完全吻合
```

## 4. 子程序 (Sub) 结构

子程序**没有**独立的头部结构，就是一段连续的指令流，以哨兵指令结束：

```
Sub := instr* sentinel
```

### 指令布局 `th06_instr_t`

```
offset  size  type    field
0x00    4     u32     time        该指令生效的时间（帧）。相同 time 的指令同帧执行
0x04    2     u16     id          opcode 号（0..161，TH07）
0x06    2     u16     size        本指令总字节数（含 12 字节头）
0x08    2     u16     rank_mask   难度掩码，实际比较高字节 (rank_mask >> 8)
0x0A    2     u16     param_mask  参数位掩码：按格式串顺序，位i=1 表示该参数"有值"
0x0C    ...             data[]     参数数据，按 param_mask 逐项解码
```

- `size` **必须**用于步进，因为参数区长度是可变的（不同 opcode 不同）。
- TH07 的特殊规则：`id == 90` 且 `version == 7` 时，`size == 12 + 4 + 48`（固定 64 字节）。
  见 `thecl06.c:1451`。这是唯一一个不按 param_mask 解码的特例。

### 哨兵 (sentinel)

```
time = 0xFFFFFFFF, id = 0xFFFF, size = 0x000C
```

哨兵本身占 12 字节，位于子程序末尾。由于 `size=12`，哨兵之后通常紧接下一个子程序。

### 视觉指令（time / rank）

`thecl` 从原始指令流中「推导」出 `thecl_instr_time` 和 `thecl_instr_rank` 伪指令：
- 当 `time` 与上一条不同时，插入一条时间节点伪指令。
- 当 `rank_mask` 高字节与上一条不同时，插入一条难度节点伪指令。

这些**不是真实指令**，只是便于阅读的注释。真正的执行语义是：
> 子程序内所有指令按 (time, 顺序) 排序，逐帧推进时间游标，`time <= 当前帧` 的指令全部执行。

---

## 5. 参数编码

TH07 属于 `pre_th8`。参数类型由 opcode 的格式串决定（见指令表），
类型字符含义（`thecl06.c` 的 `th06_value_from_data`）：

| 格式符 | 含义 | 大小 |
|--------|------|------|
| `d` | 32 位整数（相对偏移/绝对值） | 4 |
| `f` | float32 | 4 |
| `o` | 跳转目标的**绝对文件偏移**（生成时须减去当前指令地址） | 4 |
| `S` | 变量 ID（int16） | 2 |
| `x`/`$` | 变量 ID（int32） | 4 |
| `s` | 负数 = 局部变量，正数 = 全局变量（依版本） | 2 |
| `z` | 以 NUL 结尾的字符串 | 变长 |

**关键**：`param_mask` 中每一位对应格式串中的一个参数位置。
位为 0 表示该参数使用"默认值/省略"，此时**不占字节**（部分版本除外）。
这是 ECL 能节省空间的原因，也是解析器最容易出错的地方。

---

## 6. 校验结果

对全部 8 个文件执行严格解析，要求每条指令的 `size` 步进后
**精确落在下一个子程序起始偏移**（最后一个落在 `0xFFFFFFFF` 哨兵之后）：

| 文件 | 子程序 | 指令数 | 区域校验 |
|------|--------|--------|----------|
| ecldata1 | 58 | 1443 | PASS |
| ecldata2 | 77 | 2202 | PASS |
| ecldata3 | 60 | 1797 | PASS |
| ecldata4 | 153 | 4798 | PASS |
| ecldata5 | 78 | 1885 | PASS |
| ecldata6 | 74 | 2347 | PASS |
| ecldata7 | 126 | 2438 | PASS |
| ecldata8 | 136 | 3009 | PASS |
| **合计** | **762** | **19919** | **100%** |

出现过的 opcode 共 **141** 个（去重），最大 id = **161**。

### 与 thtk 的交叉验证

用 thtk 的 `thecl -d 7` 独立导出，逐子程序对比指令数：

- 子程序数量：**8/8 文件完全一致**
- 自写解析器在**全部 762 个子程序**上通过边界校验
- 唯一差异：每个文件的**最后一个**子程序，thtk 报出的指令数明显偏多

**差异原因已定位**：thtk 的 `thecl06.c:1069` 用
`while (raw_instr->time != 0xffffffff && raw_instr->size)` 判断结束，
但 `raw_instr` 在 `offset == 0xFFFFFFFF` 时仅 `break`，
其外层循环仍会继续读取**越过哨兵**的 Timeline 区数据，
把 timeline 结构误当作指令。

> 结论：这是 thtk **导出器的显示行为**，不影响其正确性（timeline 区
> 确实是以合法 `size` 自洽的字节流，所以不会崩溃）。
> 但若要逐条比对语义，**应以本仓库解析器为准**——
> 哨兵之后的字节属于 Timeline 段，必须单独解析。

`0..161` 中未在任何关卡出现的 id：
```
23, 29, 51, 53, 58, 60, 61, 68, 70, 71, 77, 83, 86, 88, 109, 123, 127, 129, 130, 134, 147
```
共 21 个。这些是**未使用/内部专用** opcode，但与已用 opcode 同属一张分发表，
反汇编时必须同样还原（敌人 AI、Boss 专用指令多在此列）。

---

## 7. 复现步骤

```powershell
# 1. 解包 th07.dat
python tools/pbg4.py extractall th07.dat work/th07_dat

# 2. 用 thtk 导出可读文本（需要 -d 7）
thtk-bin-12\thecl.exe -d 7 work\th07_dat\ecldata1.ecl work\ecldata1.txt
thtk-bin-12\thecl.exe -d 7 -r work\th07_dat\ecldata1.ecl work\ecldata1_raw.txt

# 3. 结构化解析 + 校验
python tools/ecl_dump.py work/th07_dat/*.ecl
```

---

## 8. 未解细节（待办）

- [ ] `timeline_count` 与实际槽位数的语义确认（16 是硬上限还是可变）
- [ ] 未使用槽位填 0 的规则，以及游戏在运行期如何处理 0 偏移
- [ ] `param_mask` 位 0 的语义（第一个参数是否恒存在）
- [ ] `id == 90` 特例的 48 字节结构（全局变量访问）
- [ ] stage -> ecldataN 的映射从反汇编证实
