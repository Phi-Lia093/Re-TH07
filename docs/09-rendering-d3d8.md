# TH07 渲染子系统

> 状态：**D3D8 初始化 / 相机投影 / 设备状态 已解出**；绘制调用部分待补。
> 结论全部来自 `th07.exe` 反汇编。

---

## 1. D3D8 的接入方式（重要前提）

`th07.exe` 的导入表**只从 `d3d8.dll` 导入一个符号**：

```
d3d8.dll  →  Direct3DCreate8   (IAT 0x0048d25c)
```

其余全部通过 **COM vtable** 动态调用。这决定了逆向方法：
不能靠扫描调用约定猜方法，必须从 `Direct3DCreate8` 出发逐层追踪。

| 全局变量 | 类型 | 来源 |
|---------|------|------|
| `DAT_00575954` | `IDirect3D8*` | `Direct3DCreate8(0x78)` |
| `DAT_00575958` | `IDirect3DDevice8*` | `IDirect3D8::CreateDevice` 的输出参数 |

```c
// FUN_00434a40
DAT_00575954 = Direct3DCreate8(0x78);       // 0x78 = 120 = D3D_SDK_VERSION
```

---

## 2. 设备创建参数

```c
hr = IDirect3D8::CreateDevice(
    adapter     = 0,                 // D3DADAPTER_DEFAULT
    deviceType  = 1,                 // D3DDEVTYPE_HAL
    hFocusWindow= DAT_00575c20,
    behavior    = 0x40,              // D3DCREATE_FPU_PRESERVE
    presentParams = local_50,
    ppDevice    = &DAT_00575958);
```

### 2.1 失败回退链

```c
if (FAILED(hr 0x40)) {
    hr = CreateDevice(..., behavior = 0x20, ...);   // D3DCREATE_SOFTWARE_VERTEXPROCESSING
}
```

即：**先尝试 FPU_PRESERVE，失败则退回软件顶点处理**。

### 2.2 呈现参数 `D3DPRESENT_PARAMETERS`

```c
local_50[0] = 0x280;    // BackBufferWidth  = 640
local_50[1] = 0x1e0;    // BackBufferHeight = 480
local_3c = 3;           // 见下表
local_34 = 1;
local_30 = 1;
local_2c = 0x50;        // 80
local_28 = 1;
```

字段按 `D3DPRESENT_PARAMETERS` 顺序解释：

| 字段 | 值 | 含义 |
|------|-----|------|
| BackBufferWidth | **640** | |
| BackBufferHeight | **480** | |
| BackBufferFormat | 依分支 | |
| BackBufferCount | 1 | |
| MultiSampleType | 0 | 无多重采样 |
| SwapEffect | **1 (COPY)** | 注意：TH07 用 COPY 而非 DISCARD/FLIP |
| hDeviceWindow | `DAT_00575c20` | |
| Windowed | 1 | 窗口化优先 |
| EnableAutoDepthStencil | 1 | |
| Flags | `0x50` (?) / `0x28` | |

> `SwapEffect = D3DSWAPEFFECT_COPY (1)` 是 TH07 的一个特征，
> **重制版用双缓冲 + vsync 会改变帧时序感知**，需要留意。

---

## 3. 相机与投影（完整解出）

### 3.1 透视投影矩阵 `FUN_00461dd8`

```c
void perspective(float *m, float fov, float aspect, float znear, float zfar) {
    float c = cos(fov * 0.5);
    float s = sin(fov * 0.5);
    float cot = c / s;                 // = cot(fov/2)

    m[0]  = cot / aspect;
    m[5]  = cot;
    m[10] = zfar / (zfar - znear);
    m[11] = 1.0;                       // ← 注意：D3D 左手系惯例
    m[14] = -(m[10] * znear);
    // 其余为 0
}
```

**这是标准 D3D 左手系投影矩阵**（`m[11] = 1` 而非 `-1`）。

### 3.2 视图矩阵 `FUN_004621a0`（LookAt）

```c
// 由 eye、target、up 构造
dir   = normalize(target - eye);
right = normalize(cross(up, dir));
up'   = cross(dir, right);

m[0..2]   = right;
m[4..6]   = up';
m[8..10]  = dir;
m[12..14] = -dot(axis, eye);
```

标准的**左手系 LookAt**。

### 3.3 2D 场景的实际参数（`FUN_004080xx`）

```c
halfW  = DAT_00575a20 / 2.0;          // 屏幕宽/2
halfH  = DAT_00575a24 / 2.0;          // 屏幕高/2
aspect = DAT_00575a20 / DAT_00575a24;
fov    = 0x3ea0d97c;                  // = π/10 = 0.31415927 rad = 18.000°
zfar   = 0x461c4000;                  // = 10000.0
znear  = 1.0;
```

**`fov` 精确等于 π/10（18°）** —— 这是一个刻意选定的整数角度，不是随机值。

调用：

```c
build_view(&DAT_00575998, eye = (halfW, halfH, -znear), target = (halfW, halfH, 0), up = (0,1,0));
build_projection(&DAT_005759d8, fov=π/10, aspect, 1.0, 10000.0);
SetTransform(2 /* D3DTS_VIEW */,       &DAT_00575998);
SetTransform(3 /* D3DTS_PROJECTION */, &DAT_005759d8);
```

### 3.3.1 为什么 2D 精灵需要透视投影

投影矩阵给出 `cot(fov/2) = 6.3138`。在 D3D 中：

```
ndc_y = view_y * cot(fov/2) / view_z
```

**`view_z` 直接充当缩放除数**。实测不同 z 下 1 单位高度的屏幕占位：

| 精灵所在 z | 1 单位高度 ≈ | 说明 |
|-----------|-------------|------|
| z=1 | 1515 px | 极近 |
| z=2 | 758 px | |
| **z=5** | **303 px** | |
| z=10 | 152 px | 常规精灵平面 |
| z=20 | 76 px | 远景层 |

这说明 TH07 的 2D 精灵被放在 **z ≈ 5~20** 的平面上，
**靠 z 值统一控制缩放与前后层次**。

> **这是"伪 3D"的真正机制**：
> 不是简单的 2D 卷轴，而是**所有精灵共享一个透视相机**，
> 通过 z 实现缩放、视差和层级。背景（z 更大）自然显得更远更小。

**重制要点**：若改用正交投影，会**丢失全部 z 缩放与视差**。
必须复刻「透视投影 + z 分层」这一方案。

### 3.4 3D 背景的相机（`FUN_004082b0`）

```c
eye    = param_1 + 0x51f8（含 +0x5204 等偏移）；
build_view(&DAT_00575998, param_1 + 0x51f8, &local_10, param_1 + 0x5210);
build_projection(&DAT_005759d8,
                 fov = *(float*)(param_1 + 0x5234),
                 aspect = W / H,
                 znear = 0x41f00000,   // = 30.0
                 zfar  = 0x44e10000);  // = 1800.0
SetTransform(2 /* D3DTS_VIEW */,       &DAT_00575998);
SetTransform(3 /* D3DTS_PROJECTION */, &DAT_005759d8);
```

**背景相机参数**：`znear = 30.0`、`zfar = 1800.0`，FOV 由场景数据给出。

> 这证明 3D 背景是**真正的 3D 场景**（有独立相机、近远裁剪面），
> 而不是 2D 卷轴。重制时需要建立独立的背景相机。

---

## 4. 设备状态（按参数常量分类）

> **方法**：本 build 中 vtable 偏移与 d3d8.h 的槽位编号存在系统性偏差
> （例：偏移 `0xfc` 按头文件应为 `GetVertexShaderConstant`，但传入参数
> `(0, 4, 2)` 明确是 `SetTextureStageState(0, D3DTSS_MAGFILTER, D3DTEXF_LINEAR)`）。
> 因此**不依赖槽位编号**，改用 D3D 常量的取值空间来识别方法：
> `(stage, D3DTSS_*, value)` → SetTextureStageState；
> `(D3DTS_*, matrix)` → SetTransform。

### 4.1 已确证的纹理阶段状态

| 状态 | 值 | 含义 |
|------|-----|------|
| `D3DTSS_COLOROP` | `SELECTARG1 (2)` | 贴图颜色**直接输出** |
| `D3DTSS_COLOROP` | `MODULATE (4)` | 贴图 × 顶点色 |
| `D3DTSS_ALPHAOP` | `SELECTARG1 (2)` | 贴图 alpha 直接输出 |
| `D3DTSS_ALPHAOP` | `MODULATE (4)` | alpha 相乘 |
| `D3DTSS_COLORARG1` | `0 (DIFFUSE)` / `2 (TEXTURE)` | |
| `D3DTSS_COLORARG2` | `0 (DIFFUSE)` / `3 (CURRENT)` | |
| `D3DTSS_MAGFILTER` | `LINEAR (2)` | 放大线性滤波 |
| `D3DTSS_MINFILTER` | `LINEAR (2)` / `POINT (1)` | 缩小时两套 |
| `D3DTSS_MIPFILTER` | `NONE (0)` | **不生成 mipmap** |

### 4.2 变换设置（已确证）

反汇编原文：

```c
FUN_004621a0(&DAT_00575998, &local_3c, &local_30, &local_24);       // LookAt
FUN_00461dd8(&DAT_005759d8, local_18, local_14, 1.0f, 10000.0f);    // perspective
SetTransform(2, &DAT_00575998);     // 参数 2
SetTransform(3, &DAT_005759d8);     // 参数 3
```

结合 `d3d8types.h` 的常量：

```
D3DTS_VIEW       = 2
D3DTS_PROJECTION = 3
D3DTS_TEXTURE0   = 16
D3DTS_WORLD      = 256
```

| 参数 | 常量 | 矩阵变量 | 构造函数 |
|------|------|---------|---------|
| `2` | **D3DTS_VIEW** | `DAT_00575998` | `FUN_004621a0`（LookAt） |
| `3` | **D3DTS_PROJECTION** | `DAT_005759d8` | `FUN_00461dd8`（fov/cot） |
| `0x100` | **D3DTS_WORLD** | `local_c4` | — |
| `0x10` | **D3DTS_TEXTURE0** | `local_44` | — |

**结论**：
- `DAT_00575998` = **视图矩阵**（由 LookAt 生成）
- `DAT_005759d8` = **投影矩阵**（由 fov/aspect/znear/zfar 生成）

两者与 `SetTransform` 的参数完全对应，**不存在歧义**。

> 过程中我一度把这两个矩阵写反，又一度怀疑常量值。
> 最终以「构造函数的参数语义 + SetTransform 的常量」双重对账确定如上。

### 4.3 无法确证的部分

以下状态在导出文本中**未找到带常量的调用**，不作断言：

- `D3DRS_ZENABLE` —— 未见明确设置点
- `D3DRS_ALPHABLENDENABLE` / `SRCBLEND` / `DESTBLEND`
- `D3DRS_CULLMODE`

这些很可能通过 **StateBlock**（`BeginStateBlock`/`CaptureStateBlock`/
`ApplyStateBlock`）批量设置，需要进一步追踪。

### 4.1 两种纹理阶段配置

```
配置 A（贴图直接输出）: COLOROP = SELECTARG1, ALPHAOP = SELECTARG1
配置 B（贴图 × 顶点色）: COLOROP = MODULATE,    ALPHAOP = MODULATE
```

`MODULATE` 配合 `COLORARG1 = DIFFUSE(0)` 意味着：
**顶点色（RGB）与 alpha 都与贴图相乘** —— 这是 TH07 实现
「同一张子弹贴图染成 8 种颜色」的方式（见 `etama.anm` 的彩色子弹）。
**重制版必须保留顶点色调制**，否则子弹颜色无法还原。

### 4.2 色键

`D3DTSS_COLORKEY` 配合 `D3DCOLOR`：
TH07 的 ANM 有 `colorkey` 字段（`0xff000000` 或 0），
用于**纯色抠图**（无 alpha 通道的图）。

---

## 5. 与 ANM 的关系

渲染流程（推断，部分待验证）：

```
1. ANM 头部 → 建贴图 (THTX 原始像素 → D3D 纹理)
2. 精灵表 → 每个 sprite 的 UV 矩形
3. ANM 脚本 → 每帧的 (x, y, scale, rotation, alpha, color)
4. 按 z 排序 → 设置顶点色与纹理 → DrawPrimitiveUP
```

贴图解码已在 `docs/07-rendering-anm.md` 完成，导出验证通过。

---

## 6. 重制实现建议（OpenGL 3.3）

| D3D8 | OpenGL 3.3 |
|------|-----------|
| 透视投影（左手系） | 自己构造同样的投影矩阵（`m[11]=1`） |
| LookAt | 自己构造视图矩阵 |
| `D3DRS_ZENABLE=FALSE` | `glDisable(GL_DEPTH_TEST)`（2D 精灵） |
| `D3DRS_ZWRITEENABLE` | `glDepthMask` |
| `COLOROP=MODULATE` | 着色器里 `frag *= vertexColor` |
| `MAGFILTER=LINEAR` | `GL_LINEAR` |
| `MIPFILTER=NONE` | 不生成 mipmap |
| `COLORKEY` | 片元丢弃 `if (color == key) discard;` |
| `SwapEffect=COPY` | 双缓冲 |

### 6.1 必须复刻的三个要点

1. **透视 + z 分层**：2D 精灵用透视投影，靠 z 值分层级
2. **顶点色调制**：子弹/特效靠顶点色染色
3. **左手系矩阵**：`m[11] = 1`，否则整个场景会镜像

---

## 7. 待完成

- [ ] 绘制调用（DrawPrimitiveUP）的具体顶点格式与批量策略
- [ ] 混合状态（`SRCBLEND`/`DESTBLEND`）的完整组合
- [ ] 背景 3D 层与 2D 精灵层的绘制顺序
- [ ] `SetVertexShader` 是否有自定义着色器（TH07 时代可能只有固定管线）
- [ ] 视口与分辨率缩放处理

---

## 附：两个不同的 FOV（第 32 轮补充）

之前记录主投影 `fov = pi/10 (18 度)`。后续发现**还存在第二个 FOV**：

| 常量 | 值 | 角度 | 用途 |
|------|-----|------|------|
| `0x3ea0d97c` | pi/10 | 18 度 | **主投影**（精灵/游戏对象） |
| `0x3f060a92` | **pi/6** | **30 度** | **背景相机**（3D 背景层） |

### 证据

`+0x5234` 是相机结构的 FOV 字段，在初始化时被写入 `0x3f060a92`：

```c
*(undefined4 *)(cam + 0x5234) = 0x3f060a92;   // pi/6
```

随后该结构的前 16 个 float（`+0x51f8` 起）被复制到 `+0x50f8` 和 `+0x5138`，
这两个位置正是 `cam_apply_matrices` 提交给 D3D 的矩阵。

### 重制版影响

**两个相机不能共用一个 FOV。** 否则：
- 用 pi/10 渲染背景 → 背景过度放大
- 用 pi/6 渲染精灵 → 精灵变小、深度感丢失
