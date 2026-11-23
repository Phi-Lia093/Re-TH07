# 二进制分区图（重要结构性发现）

> 通过函数区间 + 字符串特征确定代码分区。
> 这直接决定了剩余工作量：**592 个函数（约一半剩余量）属第三方库，可整体排除。**

---

## 1. 分区总览

| 地址区间 | 函数数 | 内容 | 处理方式 |
|---------|-------|------|---------|
| `0x401000` - `0x450000` | ~550 | **游戏核心逻辑** | 需精读 |
| `0x450000` - `0x461000` | 104 | **游戏 UI/音频/录像** | 需精读 |
| `0x461000` - `0x470000` | 212 | **数学/图形库** | 可排除 |
| `0x470000` - `0x4A0000` | 380 | **zlib + libpng + CRT** | 可排除 |
| 总计 | 1248 (FUN_*) | | |

### 1.1 分区依据

**`0x450000-0x461000`（游戏代码）** 的字符串特征：

```
data/title/title00.jpg
data/title/select00.jpg
bgm/th07_01.mid
./replay/th7_%.2d.rpy
```

**`0x461000-0x470000`（数学/图形库）**：

```
1.0.5          ← 库版本号
```

**`0x470000-0x4A0000`（zlib/PNG）**：

```
incorrect data check
Out of Memory
invalid chunk type
Ignoring bad adaptive filter type
invalid bit length repeat
invalid distance code
```

---

## 2. 已确认的库函数

### 2.1 zlib（可完全排除）

| 地址 | 行数 | 依据 |
|------|------|------|
| `FUN_004790a8` | 485 | `invalid bit length repeat` |
| `FUN_0047a4e6` | 315 | `invalid distance code` |
| `FUN_00471eab` | — | inflate 相关 |

**结论**：TH07 使用 **zlib 1.1.x** 解压 PNG。
重制版直接用系统 zlib 即可，无需照抄。

### 2.2 libpng（可完全排除）

| 地址 | 行数 | 依据 |
|------|------|------|
| `FUN_0046f514` | 51 | `NULL row buffer` |
| `FUN_004696f8` | 28 | png_* 辅助 |

**结论**：使用 **libpng** 读取 `.jpg`/`.png` 纹理。
重制版用 stb_image 或 SDL_image 替代。

### 2.3 .NET 运行时（可排除）

| 地址 | 行数 | 依据 |
|------|------|------|
| `FUN_0047fc6b` | 476 | `mscoree.dll` |

**结论**：某依赖库（可能是 DirectShow）静态链接了 .NET 启动器。
**TH07 本体不使用 .NET。**

### 2.4 CRT

| 地址 | 行数 | 依据 |
|------|------|------|
| `FUN_0048178f` | 698 | 无字符串，纯代码 |
| `FUN_00484b39` | 415 | 无字符串 |
| `FUN_00466499` | 389 | 无字符串 |
| `FUN_0048b8a0` | 25 | `__ftol` |
| `FUN_00480779` | 5 | `LeaveCriticalSection` |
| `FUN_004816f4` | 7 | `_terrno` |
| `FUN_0048bb40/0x48bbf0` | 8 | 浮点转换 |
| `FUN_0047d13c` | — | `__vsprintf` |

### 2.5 DirectX/DirectShow

`0x460000` 附近的 212 个函数中，包含：

- DirectDraw Surface 操作（返回 `0x80004005` = `E_FAIL`，操作 `+0x1050`/`+0x1054`/`+0x1058` 宽高和状态）
- 色彩空间转换

**结论**：DirectShow/DirectDraw 的静态链接部分。

---

## 3. 对剩余工作的影响

### 3.1 修正后的工作量

```
原始: 1147 个未命名函数
排除: ~592 个（库代码）
实际需处理: ~555 个
```

**工作量减少约 52%。**

### 3.2 游戏代码的实际分布

| 区间 | 内容 |
|------|------|
| `0x401000-0x420000` | ECL/ANM 虚拟机、渲染核心 |
| `0x420000-0x440000` | 关卡、玩家、子弹、碰撞 |
| `0x440000-0x450000` | UI 绘制、场景 |
| `0x450000-0x461000` | 标题、音乐室、录像、结算 |

---

## 4. 工具支持

### 4.1 分区过滤

```powershell
# 只看游戏代码区间的未命名函数
python tools/cluster_objects.py      # 已自动排除库区
python tools/propose_names.py        # 提案中仍含库函数，需手工过滤
```

**建议**：在 `propose_names.py` 中加入区间过滤，
只对 `0x401000-0x461000` 生成提案。

### 4.2 判断新函数是否属库

```powershell
python tools/dump_batch.py --names FUN_xxxxxxxxxxx
```

看是否有如下特征：

| 特征 | 判定 |
|------|------|
| 返回 `0x8xxxxxxx` | COM HRESULT → 库 |
| 含 `png_`/`inflate`/`deflate` 类逻辑 | zlib/PNG |
| 操作 `+0x1050`/`+0x1054` 宽高 | DirectDraw |
| 纯 CRT 名（`_errno`/`__ftol`） | CRT |
| 无字符串纯算法 | 需看内容 |

---

## 5. 待确认

- [ ] `0x461000-0x470000` 具体是哪个库（DirectShow？自研图形库？）
- [ ] `0x450000-0x461000` 中哪些是游戏逻辑、哪些是库
- [ ] 是否存在游戏逻辑混入库区间的情况
