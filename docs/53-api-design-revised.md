# API 设计（修订版）：保留 ins 风格原语，算术交给 Lua

> **设计原则（用户定）**：
> 1. **全局 API 做成最大公约数**，统筹 8 关
> 2. **保留原版 ins 一样的对象接口**（原版设计得好的话）
> 3. **只把 `add`/`fadd`/`sin` 这类不优雅的算术做成 Lua 内部的**
> 4. **不要过于专一妖妖梦**

---

## 1. 核心洞察：原版 opcode 是「字段设置原语」

看高频 opcode 的实际形态：

| op | 语义 | 粒度 |
|----|------|------|
| `op4/5` | `var = a` | 赋值 |
| `op19/20` | `var = a ± b` | 算术 |
| `op54` | 分阶段转向 | **对象操作** |
| `op95` | 切换 ANM 脚本 | **对象操作** |
| `op101` | 设置绘制偏移（不影响碰撞） | **对象操作** |
| `op102/103/104` | 设置三位标志 | **对象操作** |

**结论**：原版 ECL 的**动作类 opcode 本身就是好的对象接口**。
它们细粒度、正交、可组合 —— 这正是一个框架应该提供的。

**我之前设计 `fire_ring{count=12,...}` 是错的** —— 那是我自己发明的
"便利 API"，而原版用 `set_move_mode` + `set_angle` + 循环就能表达，
且更通用（不限于环形）。

---

## 2. 修订后的分层

```
┌───────────────────────────────────────────────────┐
│ Lua 表达式层    算术、赋值、条件、循环             │  ← add/fadd 消失
├───────────────────────────────────────────────────┤
│ 对象原语层     ins 风格：细粒度对象操作           │  ← 保留原版设计
├───────────────────────────────────────────────────┤
│ 便利层         常用组合（可选，内容包可不用）     │  ← 最大公约数
├───────────────────────────────────────────────────┤
│ 引擎层         实体、物理、渲染、音频             │
└───────────────────────────────────────────────────┘
```

### 2.1 Lua 表达式层（消掉 add/fadd）

```lua
-- 原 ECL
-- op4  &v[0], 100
-- op19 &v[1], &v[0], 50
-- op20 &v[2], &v[1], 10

-- Lua 直接写
local v0 = 100
local v1 = v0 + 50
local v2 = v1 - 10
```

**sin/cos/atan 用 Lua 内置 `math` 库**：

```lua
enemy.angle = math.atan(dy, dx)
enemy.speed = math.sin(t * 0.1) * 2 + 3
```

### 2.2 对象原语层（保留 ins 风格）

```lua
-- 位置与速度
enemy:set_pos(x, y)
enemy:set_speed(speed)
enemy:set_angle(angle)
enemy:set_vel(vx, vy)

-- 运动模式（对应原版 op75/76/54）
enemy:set_move_mode(MOVE_LINEAR)
enemy:set_move_mode(MOVE_ACCEL, ax, ay)
enemy:turn_to(angle, frames)        -- 分阶段转向（op54）

-- 绘制偏移（op101）—— 注意：不影响碰撞
enemy:set_draw_offset(x, y, z)

-- 动画（op95）
enemy:set_anim("attack_a")

-- 标志位（op102/103/104）
enemy:set_flag(FLAG_INVULN, true)

-- 子弹（原版 op 中的 bullet 设置）
bullet:set_speed(v)
bullet:set_angle(a)
bullet:set_accel(a)
bullet:set_homing(turn_rate, lifetime)
```

**这些接口的命名不绑定任何作品**，红魔乡/永夜抄也能用。

### 2.3 便利层（可选，最大公约数）

**只放跨作品通用的模式**，且内容包**可以不用**：

```lua
-- 这些是"糖"，底层仍是上面的原语
stg.fire_ring{count, speed, angle}
stg.fire_spread{count, spread, speed, angle}
stg.wait(frames)
stg.repeat_n(n, fn)
```

**关键区别**：便利层是**内容包的助手库**，不是引擎 API。
框架本身只提供原语。

---

## 3. 框架 API 的最大公约数

### 3.1 实体类型（跨作品通用）

| 类型 | 说明 | 不同作品的差异 |
|------|------|---------------|
| `Actor` | 有位置/速度/碰撞的基类 | — |
| `Enemy` | 敌机 | HP、掉落规则由内容包配 |
| `Boss` | Boss（是 Enemy 的特化） | 血条段数由内容包配 |
| `Bullet` | 子弹 | 类型表由内容包配 |
| `Item` | 道具 | 类型/价值由内容包配 |
| `Laser` | 激光 | 有/无由内容包定 |
| `Effect` | 特效 | 精灵表由内容包配 |
| `Player` | 自机 | SHT 参数由内容包配 |

### 3.2 引擎服务（跨作品通用）

```cpp
namespace stg {
    // 时间
    int  frame();                 // 当前帧号
    void time_scale(float, int);  // 时间缩放（慢动作）

    // 查询
    const std::vector<Actor*>& actors();
    Actor* nearest_enemy(Vec2 from);

    // 生成
    Actor* spawn_enemy();
    Actor* spawn_bullet(BulletDesc);

    // 音效
    void play_se(const std::string& name);
    void play_bgm(const std::string& name);

    // 随机（可确定性回放）
    float rand01();
    int   rand_int(int lo, int hi);
}
```

**这些 API 里没有任何 th07 专有名词。**

---

## 4. 内容包的职责

内容包提供**数据与行为**，不提供引擎：

```toml
# content/th07/config/entities.toml
[bullet.ball_red]
sprite = "eff/ball_red"
hitbox = 2.5
layer  = 1

[item.power]
value  = 1
sprite = "item/power"

[enemy.fairy_blue]
hp       = 10
drop     = ["item.power:2"]
anim     = "fairy"
```

```lua
-- content/th07/scripts/stages/stage01.lua
local e = spawn_enemy("fairy_blue")
e:set_pos(192, -20)
e:set_move_mode(MOVE_LINEAR)
e:set_speed(2.0)
e:set_angle(math.pi / 2)

repeat_n(3, function(i)
    if i > 0 then wait(30) end
    e:fire{
        count = 5,
        spread = math.pi / 6,
        speed = 3.0,
        angle = "player",
    }
end)
```

---

## 5. 为什么这个设计跨作品可用

| 作品 | 主要差异 | 框架如何处理 |
|------|---------|-------------|
| TH06 红魔乡 | 无樱点、宝石道具、简单判定 | 内容包配置，框架不感知 |
| TH07 妖妖梦 | 樱点、慢动作、6 层判定 | 内容包配置 + Lua 行为 |
| TH08 永夜抄 | 人间/妖怪双人、不死时间 | 内容包用 Lua 实现 |
| 旧作 | 完全不同的脚本 | 新写 Lua，需框架原生接口 |

**框架提供的原语足够表达所有这些**，因为它们本质都是「位置/速度/角度/标志/生成」的组合。

---

## 6. 与 OpenSTG 半成品的关系

`D:\OpenSTG` 已确定两件关键事：

1. **SDL3 + Lua + C**（框架可用 C++20 替换，但绑定思路相同）
2. **Lua 协程 + 调度器实现 `wait()`**

```c
// OpenSTG 的做法
static int l_wait(lua_State* L){
    int frames = luaL_checkinteger(L, 1);
    add_delay_task(frames, resume_lua, task);
    return lua_yield(L, 0);
}
```

**这是正确的核心机制**，我会沿用：

```python
# 新框架（C++）
sol::function_result resume_frame(sol::thread& co) {
    return co.resume();     # yield 表示本帧结束
}
```

**OpenSTG 的 `task` 调度器也保留了** —— 适合表达"延迟 N 帧"和"每 N 帧执行"。

---

## 7. 待确认

1. **原语层命名**：用 `enemy:set_pos()` 还是 `ins_pos(enemy, x, y)`？
   - 前者面向对象，后者更接近原版
   - 我倾向**前者**（更现代），但保持语义 1:1

2. **便利层归属**：放在引擎还是内容包？
   - 我倾向**内容包的 `scripts/lib/`**，框架不带

3. **是否保留 ECL 变量模型**：还是完全用 Lua 局部变量？
   - 完全用 Lua 局部变量（聚合后不需要模拟）

---

## 8. 原版发射器接口（**已完整解码，直接采用**）

`docs/03` §6.1 显示 `ins_64 ~ ins_72` 是 **9 种子弹发射器，同一个实现**：

```c
参数（按 mask 位）：
  bit0 (i) : 弹种/形状 ID
  bit1 (i) : 数量
  bit2 (i) : 扩散角度 ↑
  bit3 (i) : 扩散角度 ↓
  bit4 (f) : 角度
  bit5 (f) : 速度
  bit6 (f) : 加速度
  bit7 (f) : 速度变体

位置 = 自身位置 + 偏移(+0x2b74/78/7c)
难度修正：数量/角度按难度插值
网格上限：0x400 发
```

### 8.1 真实数据样本

```
op64  [shape=393216, n=2,  spr=1, angle=2.0, speed=1.0, accel=0,   ?, flags=516]
op66  [shape=393221, n=10, spr=1, angle=1.5, speed=1.0, accel=0,   ?, flags=517]
op69  [shape=393219, n=8,  spr=1, angle=2.5, speed=1.0, accel=0,   ?, flags=2]
```

**这是一个设计良好的接口**：8 个正交参数 + 9 种变体 + 网格化。

### 8.2 对应的 Lua API

```lua
-- 直接对应原版 ins_64..72
enemy:fire{
    shape  = 1,              -- 弹种
    count  = 8,              -- 数量
    spread = math.pi / 4,    -- 扩散角
    angle  = math.pi / 2,    -- 中心角度
    speed  = 3.0,
    accel  = 0.0,
    flags  = 0,
}

-- 变体（对应 ins_65..72 的不同默认值）
enemy:fire_v(2, {count = 5, angle = "player", speed = 4.0})
```

**注意**：`angle = "player"` 是便利写法，引擎会解析为目标方向。

### 8.3 其他生成原语

```lua
enemy:fire_reuse()                       -- op77，复用上次参数
enemy:fire_laser{a, b, c, d, e, f}       -- op82/83
enemy:spawn_child_ecl(sub_index)         -- op92，创建子 ECL 实例
```

**这些都是原版设计良好的部分，直接保留语义。**

---

## 9. 修订：原语 vs 便利的最终划分

### 9.1 **引擎原语**（框架提供，跨作品通用）

```lua
-- 实体
actor:set_pos(x, y)
actor:set_vel(vx, vy)
actor:set_speed(v)
actor:set_angle(a)
actor:set_draw_offset(x, y, z)
actor:set_anim(name)
actor:set_flag(id, on)

-- 发射
enemy:fire{shape, count, spread, angle, speed, accel, flags}
enemy:fire_laser{...}
enemy:spawn_child_ecl(n)

-- 时序
wait(frames)

-- 引擎
stg.rand01()
stg.play_se(name)
stg.time_scale(factor, frames)
```

### 9.2 **内容包助手**（`scripts/lib/`，不属于框架）

```lua
-- 这些是"糖"，建立在原语之上
function fire_ring(e, count, speed)
    e:fire{
        shape = 1, count = count, speed = speed,
        angle = math.pi * 2 / count,
    }
end

function face_player(e)
    e:set_angle(angle_to(e.pos, player.pos))
end
```

**框架不带这些** —— 因为不同作品可能有不同的"常用模式"。

---

## 10. 为什么这才是"最大公约数"

| 原语 | TH06 | TH07 | TH08 | 旧作 |
|------|------|------|------|------|
| `set_pos/vel/angle` | ✅ | ✅ | ✅ | ✅ |
| `fire{shape,count,...}` | ✅ | ✅ | ✅ | 可能没有 |
| `fire_laser` | ❌ | ✅ | ✅ | ❌ |
| `set_flag` | ✅ | ✅ | ✅ | ✅ |
| `wait` | ✅ | ✅ | ✅ | ✅ |
| `time_scale` | ❌ | ✅ | ✅ | ❌ |

**原语是"能表达"层面，不是"必须有"。**
内容包只使用它需要的原语，框架全部提供。
