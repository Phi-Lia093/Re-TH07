# 符号恢复进度

> 每完成一个函数就勾掉。格式：`函数名 → 新符号名`。

---

## 统计

| 项目 | 数量 |
|------|------|
| 函数总数 | 1429 |
| 已恢复符号 | **55**（00_core 21 + 01_player 9 + 02_gfx 25） |
| 已文档化 | 约 30（ECL 相关） |
| 待处理 | ~1375 |

---

## 00_core.txt（已完成，21 项）

ECL 虚拟机核心 + RNG + 时钟 + D3D8 全局 + 屏幕常量。

见 `docs/15-symbol-recovery-workflow.md` §3。

---

## 01_player.txt（已完成，9 项）

| 地址 | 符号 | 状态 |
|------|------|------|
| `FUN_0043ee50` | `player_update_input` | ✅ **精读完成** |
| `FUN_00442ee0` | `player_replay_input` | ✅ 精读完成 |
| `FUN_004423e0` | `player_init` | ✅ 精读完成 |
| `FUN_00440cf0` | `player_death_update` | ✅ 精读完成 |
| `DAT_004b9e50` | `g_input_state` | ✅ |
| `DAT_004b9e58` | `g_input_prev` | ✅ |
| `DAT_004b9e60` | `g_input_hold_frames` | ✅ |
| `DAT_0062f648` | `g_flags_game` | ✅ |
| `DAT_004b9e4c` | `g_input_raw` | ✅ |

### player_update_input 精读结果（139 行）

**输入解码**：
```c
g_input_state 位定义：
  0x10 = 左    0x20 = 右    0x40 = 上    0x80 = 下    0x04 = 低速键
```

**方向编码**（写入 `player+0x241c`）：
```
1=左  2=右  3=上  4=下
5=左上 6=右上 7=左下 8=右下
```

**速度选取**（从 `player+0xb7e70` → `.sht`）：
```c
非低速 (slow==0):   直线用 sht+0x24，斜向用 sht+0x2c
低速   (slow!=0):   直线用 sht+0x28，斜向用 sht+0x30
```

**位置更新**：
```c
player+0x9cc = dx * player+0x23f0 * g_slow_factor
player+0x9d0 = dy * player+0x23f4 * g_slow_factor
player+0x930 += player+0x9cc      // X
player+0x934 += player+0x9d0      // Y
// 然后钳制到 g_field_x0..+w, g_field_y0..+h
```

**动画切换**（方向改变时）：
```
向左 → ANM 脚本 0x401     向右 → 0x403
向上 → 0x402              向下 → 0x404
```

> **重要修正**：`.sht` 指针在 **`player+0xb7e70`**，
> 不是我此前假设的全局 `DAT_00575948`（后者可能是另一份副本）。

---

## 02_gfx.txt（已完成，25 项）

见符号文件。关键结论：

### anm_bind_sprite（`FUN_0044e8e0`）

```c
instance->sprite = sprite_table + 0x60 + index * 0x40;
instance->scale_x = sprite->w / 256.0;     // 像素 → 归一化
instance->scale_y = sprite->h / 256.0;
```

**sprite 尺寸是整数像素，除以 256 归一化。**

### anm_draw_sprite（`FUN_0044efb0`）

UV 四角来自 sprite 结构的 `+0x1c / +0x20 / +0x24 / +0x28`（即 x, y, w, h）：

```c
u 坐标 = sprite->x  / atlas_w,  sprite->y  / atlas_h
v 坐标 = sprite->x+w / atlas_w, sprite->y+h / atlas_h
```

### gfx_flush_batch（`FUN_0044f5c0`）

```c
DrawPrimitiveUP(TRIANGLESTRIP, count << 1, g_quad_vb, 0x1c);
```
**28 字节顶点，每次提交累积的四边形。**

---

## 待办：巨型函数

| 地址 | 行数 | 状态 |
|------|------|------|
| `FUN_00410520` | 3350 | ✅ `ecl_interpreter` |
| `FUN_00450d60` | 1451 | 🔶 `anm_run_script`（待精读） |
| `FUN_0048178f` | 699 | ⬜（疑似 CRT 族） |
| `FUN_00420620` | 496 | ⬜ |
| `FUN_004790a8` | 486 | ⬜ |

---

## 说明

「候选符号」= **基于调用关系和已知常量的推测**，
未真正读过之前不写入符号表、不标记为完成。

已经发现并修正的推测错误：
- ~~`FUN_0044e8e0` = anm_sprite_lookup~~ → 实际是 `anm_bind_sprite`（绑定+归一化）
- ~~`FUN_0044eae0` = anm_instance_reset~~ → 实际是 `anm_sync_params`（参数同步）
- ~~`FUN_0044f9a0` = anm_draw_rotated~~ → 实际是 `anm_draw_angle`（角度为 0 时委托）
- ~~`.sht` 指针在 `DAT_00575948`~~ → 玩家用的是 `player+0xb7e70`
