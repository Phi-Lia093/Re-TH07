# ECL → Lua 聚合转译设计

> 基于已确认的四项决策：
> 1. **ECL 聚合为高层 API**
> 2. 图集保持原版
> 3. 录像只留接口
> 4. 自机先做灵梦

---

## 1. 为什么聚合是对的

### 1.1 数据说话

| opcode | 次数 | 语义 | 聚合策略 |
|--------|------|------|---------|
| `op4` | 2543 | `var = a`（int） | **直接赋值** |
| `op5` | 2279 | `var = a`（float） | **直接赋值** |
| `op19` | 653 | `var = a + b` | **直接 `a + b`** |
| `op20` | 405 | `var = a - b` | **直接 `a - b`** |
| `op41` | 857 | 子程序调用 | **Lua 函数** |
| `op95` | 643 | 切换 ANM 脚本 | **`set_anim("name")`** |

**前 4 个 opcode 占 26.5%，全是算术/赋值 —— 聚合后完全消失，变成原生 Lua 表达式。**

这正是你要求的：「良好用 Lua 算符功能，只在游戏引擎进行 call native」。

### 1.2 聚合后的规模估算

```
原始：19,919 条 ECL 指令
      ↓ 聚合
算术/赋值类（~40%）→ 内联进表达式，无代码行
控制流类（~15%）   → Lua 的 if/while/wait
动作类（~45%）     → 高层 API 调用
```

**预计产出 3,000–5,000 行 Lua**，而不是 19,919 行。

---

## 2. 聚合规则

### 2.1 算术与赋值 → 原生表达式

```lua
-- 原 ECL
-- op4  &var[0], 100          (var0 = 100)
-- op5  &var[1], 3.5          (var1 = 3.5)
-- op19 &var[2], &var[1], 2.0 (var2 = var1 + 2.0)

-- 聚合后
local var0 = 100
local var1 = 3.5
local var2 = var1 + 2.0
```

### 2.2 控制流 → Lua 结构

```lua
-- 原 ECL: 条件 + 跳转
-- 聚合后
if condition then
    ...
end

-- 等待
wait(30)          -- 原 op 的 wait 语义

-- 子程序
local function shoot_pattern_a()
    ...
end
shoot_pattern_a()
```

### 2.3 动作类 → 高层 API

```lua
-- 原 ECL: op79 (7 参数，未识别) / op67 / op64 等
-- 聚合后（需要先确定语义）
fire_ring{
    count = 12,
    speed = 4.0,
    angle_start = math.pi / 2,
    angle_step  = math.pi * 2 / 12,
}

set_anim("attack_a")
face_toward_player()

play_se("enemy_shot")
```

---

## 3. 引擎 API 设计

### 3.1 敌机控制 API

```lua
-- 位置与运动
enemy.pos      = {x, y}
enemy.vel      = {vx, vy}
enemy.move_to(x, y, frames)
enemy.move_by(dx, dy, frames)

-- 朝向与速度
enemy.angle    = math.pi / 2
enemy.speed    = 3.0
enemy.face_player()

-- 状态
enemy.hp       = 100
enemy.invuln   = 30
enemy.visible  = true
enemy.anim     = "idle"
```

### 3.2 弹幕生成 API

```lua
-- 环形
fire_ring{
    count = 12,
    speed = 4.0,
    angle = "up",            -- 或数字
    type  = "ball_red",
}

-- 扇形
fire_spread{
    count = 5,
    spread = math.pi / 3,
    speed = 3.0,
    angle = "player",
}

-- 单发
fire({
    speed = 5.0,
    angle = math.atan(dy, dx),
    type  = "needle_blue",
})

-- 追踪
fire_homing{
    speed = 3.0,
    turn_rate = 0.05,
    lifetime = 180,
}
```

### 3.3 时序 API

```lua
wait(60)                       -- 等待 60 帧
wait_until(function() ... end) -- 等待条件

repeat_n(8, function(i)
    fire({angle = math.pi * 2 * i / 8, speed = 3.0})
    wait(6)
end)
```

### 3.4 通用时间缩放（慢动作）

```lua
-- 替代原 op95 索引 10/11 的硬编码
time_scale(0.5, 120)     -- 0.5x 速度持续 120 帧
time_scale(1.0)          -- 恢复正常
```

> **注意**：TH07 的慢动作是**双重缩放**（`docs/38`）。
> 这里是**通用 API**；内容包里通过配置选择是否模拟原作的双重行为。

---

## 4. 内容包结构

```
content/th07/
├── manifest.toml
├── config/
│   ├── game.toml
│   ├── player.toml        灵梦参数（来自 SHT）
│   ├── bombs.toml         12 个 Bomb（docs/46）
│   ├── scoring.toml       计分（docs/33）
│   └── difficulty.toml
├── scripts/
│   ├── lib/               公共弹幕模式
│   ├── stages/
│   │   ├── stage01.lua
│   │   └── ... stage08.lua
│   └── dialogue/
│       └── stage01.lua
├── anm/                   动画定义（原版图集 + TOML 描述）
├── sprites/               原始图集（不重打包）
└── audio/
```

---

## 5. 关键设计细节

### 5.1 时间模型

**原版 ECL 是「执行到阻塞」**（`docs/18` §10）。
Lua 用**协程**实现同样语义：

```cpp
// C++ 侧
sol::protected_function_result run_frame(sol::coroutine& co) {
    return co.resume();
}
```

```lua
-- Lua 侧
coroutine.yield()   -- 等价于原版的"本帧结束"
wait(30)            -- 内部 yield 30 次
```

### 5.2 变量作用域

原版 ECL 有三种变量（局部 / 全局 / 跨栈继承）。
聚合后：

```lua
-- 局部 → Lua local
local hp = 100

-- 全局 → 表字段
stage.global.combo_count = 0

-- 跨栈继承 → 闭包捕获
local function pattern()
    return hp * 2       -- 自动捕获 hp
end
```

**不需要模拟原版的栈继承机制 —— 闭包天然实现。**

### 5.3 与框架的边界

**框架提供**：
- 实体生命周期
- 物理积分
- 碰撞检测
- 渲染批处理
- 音频播放

**内容包提供**：
- 敌机 AI（Lua）
- 弹幕模式（Lua）
- 数值配置（TOML）
- 动画定义（TOML）

**框架不得包含任何 th07 特有逻辑**（樱点、Bomb 类型等）。

---

## 6. 转译器设计

### 6.1 流程

```
ecldataN.ecl
    ↓ 解析（tools/ecl_dump.py 已有）
指令流 + 变量引用 + 跳转目标
    ↓ 控制流重建
基本块 + 跳转图
    ↓ 聚合规则
Lua 源码（含高层 API 调用）
    ↓ 人工修复
最终 stageNN.lua
```

### 6.2 为什么需要人工修复

**约 45% 的动作类 opcode 需要确定语义**才能聚合成正确的 API。
`docs/03` 有语义描述，但转成什么 API 需要设计。

**预计每个关卡 2-4 小时人工修复**，8 关约 **20-30 小时**。

### 6.3 验证方法

```lua
-- 生成的脚本带原始指令注释
-- 原: op4 &var[0], 100  (offset 0x1234)
local var0 = 100
```

**对照测试**：转译后脚本的**指令执行顺序**应与原版一致。

---

## 7. 开发顺序（修订）

| 阶段 | 内容 | 周 |
|------|------|-----|
| M1 | 平台层 + 窗口 + 输入 | 2 |
| M2 | 渲染 + 双相机 + 原版图集加载 | 3 |
| M3 | 实体 + 碰撞 + 运动 | 4 |
| M4 | ANM 状态机（TOML 定义） | 3 |
| M5a | **转译器骨架**（算术/控制流） | 3 |
| M5b | **动作类 API 设计 + 转译** | 3 |
| M6 | 弹幕系统 + 第 1 关 | 4 |
| M7 | 玩法完整（计分/道具/Bomb/樱点） | 4 |
| M8 | 灵梦自机 + UI | 3 |
| M9 | 音频 | 2 |
| M10 | 剩余 7 关转译 | 6 |
| **合计** | | **37 周** |

> 比原计划略少，因为聚合转译减少了 Lua 代码量和 M5 的调试面。

---

## 8. 待决事项

1. **动作类 opcode 的 API 命名**：先集中设计 20 个高频动作，其余按需
2. **原版图集加载**：直接读 THTX？还是预转换成 PNG？
   - 读 THTX：保真，但需实现解码器
   - 转 PNG：一次性工具，运行时只读 PNG（**推荐**）
3. ~~**Bomb 的实现层**~~ → **已定：纯 Lua 行为 + TOML 基础参数**

### 8.1 Bomb 实现决策依据

12 个 Bomb 的几何差异极大：

| 类型 | 槽位 | 特征 |
|------|------|------|
| 8 等分星形 | 8 | 固定角度，共享起点 |
| 随机散落 | 8 | 每弹独立起点 |
| 四角对称 | 4 | `base + offset` 累加 |
| 三连跟随 | 3 | 无弹幕 |
| 8 等分加速 | 8 | 加速 96/帧 |
| 拖尾散射 | 24 | 8 段拖尾，负初速 |
| 极密迸发 | 96 | 每帧最多 5 个 |
| 螺旋 | 96 | 96 等分 + 自旋 |
| 环状环绕 | 6 | 绕玩家旋转 |
| 水平光波 | 4 | 固定右侧 |
| 十字汇聚 | 4 | 四象限对称 |
| 超长拖尾 | 2 | 32 段拖尾 |

**纯 TOML 装不下这些差异** —— 不是参数不同，是**结构不同**。

**方案**：
- `config/bombs.toml`：通用参数（时长、缩放、音效、精灵）
- `scripts/bombs/*.lua`：每个 Bomb 的逐帧行为

估算 **~700 行 Lua**（12 个 × 40-80 行），可读性远好于 12 个 C 函数。
