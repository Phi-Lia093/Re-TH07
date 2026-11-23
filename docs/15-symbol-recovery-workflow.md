# TH07 符号恢复工作流

> 目标：把 1429 个 `FUN_xxxxxxxx` / `DAT_xxxxxxxx` 恢复成可读符号，
> 写回 Ghidra 后反编译输出直接显示真名，使重制版可照抄。

---

## 1. 基础设施（已完成）

| 组件 | 文件 | 作用 |
|------|------|------|
| 符号表 | `ghidra/symbols/*.txt` | 版本化的「地址 → 名字」映射 |
| 写回脚本 | `ghidra/scripts/th07_apply_symbols.java` | 把符号表推入 Ghidra 工程 |
| 反编译导出 | `ghidra/scripts/th07_decompile_addr.java` | 按地址反编译单个函数 |
| 普查工具 | `tools/census.py` | 函数规模与调用图统计 |
| 进度追踪 | `ghidra/symbols/PROGRESS.md` | 已完成/待办函数清单 |

### 1.1 符号表格式

```
# 注释行
FUN_00410520  ecl_interpreter    ECL VM main loop (single tick)
DAT_00575954  g_d3d8             IDirect3D8*
LAB_00411f00  ecl_cond_jump
```

第三列可选，作为函数/数据注释写入。

### 1.2 应用流程

```powershell
& 'D:\ghidra_12.2_PUBLIC\support\analyzeHeadless.bat' `
  'D:\Re-TH07\ghidra\proj' TH07 -process th07.exe -noanalysis `
  -scriptPath ghidra/scripts `
  -postScript th07_apply_symbols.java 'D:\Re-TH07\ghidra\symbols\01_ecl.txt'
```

### 1.3 验证

```powershell
# 反编译某个函数，确认显示的是新名字
-postScript th07_decompile_addr.java 0x410520 0x410600
```

**已实测有效**：应用 `00_core.txt` 后，
`FUN_00410520` 输出为 `ecl_interpreter`，
其内部的 `FUN_0040e530` 显示为 `ecl_set_ip`。

---

## 2. 命名规范

### 2.1 风格

**snake_case，`模块_动作`**

| 前缀 | 模块 |
|------|------|
| `ecl_` | ECL 虚拟机 |
| `player_` | 玩家系统 |
| `anm_` | ANM 精灵/动画 |
| `gfx_` | 渲染管线（D3D8） |
| `ui_` | 界面 |
| `snd_` | 音频 |
| `res_` | 资源加载（th07.dat） |
| `rng_` | 随机数 |
| `math_` | 数学辅助 |
| `ease_` | 缓动/插值 |
| `obj_` | 游戏对象/实体 |
| `coll_` | 碰撞 |
| `save_` | 存档/录像 |
| `dbg_` | 调试 |

### 2.2 全局变量

| 风格 | 示例 |
|------|------|
| `g_模块_名` | `g_d3d8_device`, `g_screen_width` |
| `g_模块_arr` | `g_obj_pool` |
| 表 | `g_ecl_dispatch` |

### 2.3 不确定的命名

若只知大致用途，用 `_maybe` 后缀并在注释说明：

```
FUN_0048178f  obj_update_maybe     large update loop, purpose unconfirmed
```

---

## 3. 已恢复的核心符号（00_core.txt）

| 地址 | 符号 | 确认依据 |
|------|------|---------|
| `FUN_00410520` | `ecl_interpreter` | 巨型 switch + 指令指针，文档 02 |
| `FUN_0040e5b0` | `ecl_read_var_i` | 变量 case 表，文档 02 |
| `FUN_0040edf0` | `ecl_read_var_f` | 同上 |
| `FUN_0040ec00` | `ecl_addr_var_i` | 返回写入地址 |
| `FUN_0040f3c0` | `ecl_addr_var_f` | 同上 |
| `FUN_0040e530` | `ecl_set_ip` | 设置指令指针 |
| `FUN_0041f2e0` | `ecl_spawn_instance` | 实例池分配 |
| `FUN_0041f430` | `ecl_spawn_child` | 继承全局创建子实例 |
| `FUN_004318d0` | `rng_next_u32` | 两个 16 位字拼接 |
| `FUN_00431900` | `rng_next_f01` | `rand / 4294967295.0` |
| `FUN_00431930` | `angle_normalize` | 循环加减 2π |
| `FUN_0043958d` | `clock_advance` | 帧计数 + 小数部分 |
| `FUN_0048b8a0` | `__ftol` | 读 ST0 转整型 |
| `DAT_00575954` | `g_d3d8` | `Direct3DCreate8` 返回值 |
| `DAT_00575958` | `g_d3d8_device` | `CreateDevice` 输出 |
| `DAT_00575a20` | `g_screen_width` | = 640 |
| `DAT_00575a24` | `g_screen_height` | = 480 |
| `DAT_00575ac8` | `g_slow_factor` | 慢放倍率 |
| `DAT_00575948` | `g_sht` | `.sht` 头指针 |
| `DAT_00575c20` | `g_hwnd` | 窗口句柄 |

---

## 4. 规模与优先级

### 4.1 总量

```
1429 个函数，87056 行反编译 C
```

### 4.2 按规模分层

| 层级 | 行数 | 数量（估） | 说明 |
|------|------|-----------|------|
| 巨型 | >500 | ~5 | ECL 解释器、对象更新 |
| 大型 | 200~500 | ~30 | 各系统主函数 |
| 中型 | 50~200 | ~200 | 子功能 |
| 小型 | <50 | ~1200 | getter/setter/数学辅助 |

### 4.3 优先级顺序

1. **ECL 虚拟机**（已完成主体）
2. **玩家系统**
3. **渲染管线 / ANM**
4. **对象池 / 碰撞**
5. **UI**
6. **音频**
7. **资源 / 存档**
8. **数学辅助**（最后，批量处理）

---

## 5. 每轮工作流

```
1. 从 PROGRESS.md 取下一批函数（30~60 个中小型，或 1~2 个巨型）
2. 用 th07_decompile_addr 反编译
3. 阅读并理解
4. 写入对应的 ghidra/symbols/NN_模块.txt
5. 更新 PROGRESS.md
6. 撰写/追加 docs/ 下的模块文档
7. 应用符号 → 验证
8. 提交
```

---

## 6. 验收标准

一个函数「完成」需满足：

- [ ] 有 snake_case 符号名
- [ ] 在 `docs/` 中有对应说明（至少一句话的用途）
- [ ] 关键参数/返回值已理解
- [ ] 符号已写回 Ghidra 并验证

对核心函数（玩家/渲染/ECL）额外要求：

- [ ] 有伪代码或流程描述
- [ ] 关键常量已提取
- [ ] 与已解出的数据结构（`.sht`/ANM/ECL）对应关系明确
