# 符号恢复进度

> 每完成一个函数就更新。格式：`地址 → 符号名`。

---

## 统计

| 项目 | 数量 |
|------|------|
| 函数总数 | 1429 |
| 已恢复符号 | **187** |
| 已精读函数 | **60** |
| 待处理 | ~1360 |

### 符号文件

| 文件 | 项数 | 内容 |
|------|------|------|
| `00_core.txt` | 21 | ECL VM 核心、RNG、时钟、D3D8 全局、屏幕常量 |
| `01_player.txt` | 9 | 玩家输入/初始化/死亡 |
| `02_gfx.txt` | 25 | 精灵绘制、矩阵、顶点缓冲 |
| `03_anm.txt` | 10 | ANM 解释器与变量访问 |
| `04_ui.txt` | 20 | HUD、暂停菜单、视口、难度 |
| `05_util.txt` | 11 | 日志、链表、校验和、时间重置 |
| `06_stage.txt` | 25 | 关卡主循环、实体剔除/钳制 |
| `07_scene.txt` | 17 | 场景构造、纹理加载、文件读取 |
| `08_audio.txt` | 13 | DirectSound、MIDI、WAV 解析 |
| `09_res.txt` | 9 | 统一加载器、PBG4 封包 |
| `10_math.txt` | 22 | 样条、坐标变换、数值工具 |
| `11_replay_ui.txt` | 7 | 录像列表、结束菜单 |
| `12_camera.txt` | 3 | 摄像机关键帧 VM |
| `13_bullet.txt` | 7 | 弹幕更新、对象生成器 |

### 重要：代码分区（大幅修正工作量）

见 `docs/21-binary-partition-map.md`。

| 区间 | 函数数 | 内容 | 处理 |
|------|-------|------|------|
| `0x401000-0x450000` | ~550 | 游戏核心 | 需精读 |
| `0x450000-0x461000` | 104 | 游戏 UI/音频/录像 | 需精读 |
| `0x461000-0x470000` | 212 | 数学/图形库 | **可排除** |
| `0x470000-0x4A0000` | 380 | zlib + libpng + CRT | **可排除** |

**592 个库函数可整体跳过**，实际待处理游戏函数约 **555 个**（原估计 1147）。

### 规模分布

| 行数 | 数量 | 占比 |
|------|------|------|
| <10 | 315 | 22.0% |
| 10-30 | 507 | 35.5% |
| 30-60 | 305 | 21.3% |
| 60-150 | 217 | 15.2% |
| 150-400 | 76 | 5.3% |
| 400+ | 9 | 0.6% |

**822 个函数 ≤30 行（57.5%）** —— 可批量处理。
**85 个函数 >150 行** —— 需精读。

### 可跳过

| 地址 | 判定依据 |
|------|---------|
| `FUN_004790a8` (485L) | 含 `"invalid bit length repeat"` → zlib inflate |
| `FUN_00471eab` | 同上 |
| `FUN_0047fc6b` (476L) | 含 `"mscoree.dll"` → .NET 运行时 |

---

## 已精读函数清单

| 地址 | 符号 | 行数 | 精读要点 |
|------|------|------|---------|
| `FUN_00410520` | `ecl_interpreter` | 3349 | ECL VM 主循环、161 opcode |
| `FUN_00450d60` | `anm_run_script` | 1450 | ANM VM、5 组插值器、缓动 |
| `FUN_0043ee50` | `player_update_input` | 411 | 输入位→方向→速度→位置 |
| `FUN_0044efb0` | `anm_draw_sprite` | ~90 | UV 四角来源 |
| `FUN_0044f5c0` | `gfx_flush_batch` | ~15 | DrawPrimitiveUP 提交 |
| `FUN_0044f690` | `gfx_push_quad` | ~40 | 28 字节顶点写入 |
| `FUN_0044e8e0` | `anm_bind_sprite` | 36 | 矩形绑定 + /256 归一化 |
| `FUN_0044ea20` | `anm_set_script` | 24 | 重置 + 运行到首停 |
| `FUN_00450a50` | `anm_read_var_f` | 42 | 变量 float 读 |
| `FUN_00450b20` | `anm_read_var_i` | 37 | 变量 int 读 |
| `FUN_00450ca0` | `anm_addr_var` | 27 | 变量地址（计数器） |
| `FUN_004010f0` | `anm_instance_reset` | 20 | 清 0x72 dword |
| `FUN_00401000` | `anm_reset_transform` | 20 | 变换字段清零 |
| `FUN_004394c7` | `clock_skip_frames` | 25 | 帧计数减 N |
| `FUN_00442ee0` | `player_replay_input` | ~20 | 录像输入注入 |
| `FUN_0042b603` | `ui_hud_draw` | 429 | HUD 坐标（截图双验） |
| `FUN_00402780` | `ui_pause_menu` | 334 | 暂停菜单状态机 |
| `FUN_004315f0` | `dbg_log_append` | 32 | 日志缓冲追加 |
| `FUN_00430140` | `obj_list_remove` | 45 | 双链表移除 |
| `FUN_004011b0` | `anm_reset_timers` | 31 | 两组 5 个插值器复位 |
| `FUN_0042d75a` | `save_checksum_sum` | ~20 | 字节范围求和 |
| `FUN_0042d7be` | `save_checksum_build` | ~18 | 校验和组合 |
| `FUN_0047d13c` | `__vsprintf` | — | CRT 格式化 |
| `FUN_004052d0` | `math_catmull_rom` | 7 | Catmull-Rom 样条 |
| `FUN_004325c0` | `math_polar_to_xy` | 11 | 极坐标转换 |
| `FUN_0042fab0` | `list_node_init` | 12 | 链表节点初始化 |
| `FUN_0042fb20` | `list_node_free` | 12 | 链表节点销毁 |
| `FUN_00433a90` | `obj_reset_batch` | 17 | 批量重置 0x44c 个记录 |
| `FUN_00401170` | `anm_instance_init` | 14 | AnmInstance 清零 |
| `FUN_0042f736` | `stat_add_capped` | 8 | 值增加+钳制 |
| `FUN_0042f789` | `stat_raise_max` | 8 | 上限提升 |
| `FUN_00401970` | `render_main_update` | 11 | 每帧渲染入口 |
| `FUN_004017b0` | `counter_inc_capped` | 7 | 计数器递增 |
| `FUN_004010b0` | `clock_step_ret` | 6 | 时间推进 |
| `FUN_00461bff` | `math_mat_rot_y` | 25 | Y 轴旋转矩阵 |
| `FUN_00461c7a` | `math_mat_rot_z` | 25 | Z 轴旋转矩阵 |

---

## 重要陷阱记录

### Ghidra 负号表示法

Ghidra 对 `0xff......` 开头的 32 位常量显示为负数：

| 显示 | 实际 |
|------|------|
| `-0x7fcfcfd0` | `0xff303030`（深灰 ARGB） |
| `-0x3f800000` | `0xc0800000`（-4.0f） |

**读取时必须 `& 0xffffffff` 换算**，否则会误判成坐标或颜色。

### 工程锁

Ghidra GUI 打开工程时会持有 `TH07.lock`，
headless 写回会失败（`LockException`）。
需先关闭 GUI。残留锁在确认无 java 进程后可删除。

---

## 巨型函数待办

| 地址 | 行数 | 状态 |
|------|------|------|
| `FUN_00420620` | 495 | ⬜ |
| `FUN_0042b603` | 429 | 🔶 含 HUD 坐标，部分读过 |
| `FUN_00484b39` | 415 | ⬜ |
| `FUN_00466499` | 389 | ⬜ |
| `FUN_00432990` | 380 | ⬜ |
| `FUN_004555dd` | 349 | 🔶 含 `data/title/title00.jpg` → 标题界面 |
| `FUN_00402780` | 334 | 🔶 含 `"UnPause"` → 暂停逻辑 |

---

## 下一批候选（按价值）

1. `FUN_0042b603`（429L）—— HUD 绘制，含精确坐标
2. `FUN_00402780`（334L）—— 暂停菜单
3. `FUN_004555dd`（349L）—— 标题界面
4. 30-60 行区间的 UI/资源函数批量

---

## 已修正的推测错误

记录在案避免重复踩坑：

| 猜测 | 实际 |
|------|------|
| `FUN_0044e8e0` = sprite 查找 | `anm_bind_sprite`（绑定+归一化） |
| `FUN_0044eae0` = 实例重置 | `anm_sync_params`（参数同步） |
| `FUN_0044f9a0` = 旋转绘制 | `anm_draw_angle`（角度为 0 时委托） |
| `.sht` 在 `DAT_00575948` | 玩家实际读 `player+0xb7e70` |
| `FUN_004010f0` = 清时间轴 | `anm_instance_reset`（全字段重置） |
| `FUN_00401000` = 重置帧 | `anm_reset_transform`（变换清零） |

---

## 工作流

```
1. tools/function_profile.py 取特征（调用/字符串/常量）
2. th07_decompile_addr.java 反编译
3. 精读 → 写 ghidra/symbols/NN_模块.txt
4. 更新本文件
5. 撰写 docs/ 对应章节
6. th07_apply_symbols.java 应用 → 验证
7. 提交
```
