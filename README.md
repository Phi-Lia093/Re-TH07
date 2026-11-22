# Re-TH07

**东方妖妖梦 / Perfect Cherry Blossom (TH07) —— 逆向工程与现代化重制**

本仓库做两件事：

1. **逆向**原版 `th07.exe`（Win32 / MSVC / D3D8，无壳），把游戏逻辑、
   渲染逻辑、ECL 虚拟机完整还原成文档；
2. 在此基础上用 **SDL3 + OpenGL 3.3 Core + Lua** 重制游戏。

> 原版二进制与游戏资源**不进入版本库**（见 `.gitignore`）。
> 你需要自行准备 `th07.exe` / `th07.dat` / `thbgm.dat` 放在仓库根目录。

---

## 当前进度

| 子系统 | 状态 |
|--------|------|
| `th07.dat` (PBG4) 解包 | ✅ 完成，197/197 条目 |
| ECL 容器格式 | ✅ 完成，762 子程序 100% 校验 |
| ECL 指令语义 (161 条) | ⬜ 未开始（核心任务） |
| 游戏逻辑 / 渲染 / Replay | ⬜ 未开始 |

详见 **[docs/00-plan.md](docs/00-plan.md)**。

---

## 目录结构

```
docs/            逆向文档
  00-plan.md           总计划与路线图
  01-ecl-format.md     ECL 容器格式（已验证）
tools/           零依赖 Python 工具
  pbg4.py              th07.dat 解包
  ecl_dump.py          ECL 解析与校验
thtk/            thtk 参考实现（本地 clone，不入库）
```

---

## 快速开始

### 环境

- Python 3.12+
- Ghidra 12.x（静态分析用，见 docs/00-plan.md Phase 1）

### 解包 th07.dat

```powershell
python tools/pbg4.py list th07.dat             # 列出条目
python tools/pbg4.py extractall th07.dat work/th07_dat
python tools/pbg4.py extract th07.dat ECL work/ecl.bin
```

> 注：纯 Python 的 LZSS 在 23 MB 数据上需要数分钟，属正常现象。

### 解析与校验 ECL

```powershell
python tools/ecl_dump.py --summary work/th07_dat/*.ecl     # 校验全部
python tools/ecl_dump.py work/th07_dat/ecldata1.ecl       # 详细导出
```

期望输出：

```
ecldata1.ecl        58    1443    10060     PASS
...
```

### 用 thtk 导出可读文本（对照用）

```powershell
thtk-bin-12\thecl.exe -d 7 work\th07_dat\ecldata1.ecl work\ecldata1.txt
```

> ⚠️ thtk 的导出器在**每个文件的最后一个子程序**处会越过哨兵、
> 把 Timeline 区数据误读为指令。容器级校验请以 `tools/ecl_dump.py` 为准。
> 详见 [docs/01-ecl-format.md](docs/01-ecl-format.md) §6。

---

## 技术选型

| 层 | 选择 | 理由 |
|----|------|------|
| 平台 | SDL3 | 跨平台，现代，输入/窗口/音频一体 |
| 图形 | OpenGL 3.3 Core | 兼容性最好的现代基线，能清晰映射 D3D8 固定管线 |
| 脚本 | Lua | 替代原版二进制 ECL，保留协程/时间轴语义 |
| 分析 | Ghidra 12 | 免费，Python/Java 脚本能力强 |

---

## 贡献约定

- 每条逆向结论在文档中标注证据等级：`[已验证]` / `[反汇编]` / `[推测]` / `[待查]`
- 工具必须可复现：文档中写清命令
- 不提交任何游戏二进制或解包数据
