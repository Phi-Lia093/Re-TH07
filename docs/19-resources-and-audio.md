# 资源加载与音频系统（精读）

> 来源：`res_load`（`FUN_00431330`）、PBG4 封包函数、DirectSound 音频函数。

---

## 1. 统一资源加载器（res_load）

### 1.1 关键设计：一个函数两种来源

```c
void *res_load(const char *path, int from_disk)
```

| `from_disk` | 行为 | 日志 |
|-------------|------|------|
| **0** | 从 **th07.dat** 封包解压 | `"%s Decode ... "` |
| **非 0** | 直接从磁盘读取 | `"%s Load ... "` |

**这是 TH07 资源系统的核心抽象**：
所有图片/音频/脚本都通过它加载，
开发版可从磁盘读，发布版从封包读。

### 1.2 封包分支（from_disk == 0）

```c
// 1. 从完整路径中提取文件名（去掉目录）
name = strrchr(path, '\\');  name = name ? name + 1 : path;
name = strrchr(name, '/');   name = name ? name + 1 : path;

// 2. 在封包目录中查找
size = pbg_find_size(name);
if (size == 0) {
    dbg_logf_err("error : %s is not found in arcfile.\r\n", name);
    return NULL;
}

// 3. 分配并解压
buf = malloc(size);
pbg_read_entry(name, buf);
return buf;
```

**注意**：封包内只存**文件名**，不含目录。
所以 `data/player00.anm` 在封包里就叫 `player00.anm`。

### 1.3 磁盘分支（from_disk != 0）

```c
HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
if (h == INVALID_HANDLE_VALUE) {
    dbg_logf("error : %s is not found.\r\n", path);
    return NULL;
}
size = GetFileSize(h, NULL);
buf = malloc(size);
ReadFile(h, buf, size, &read, NULL);
g_last_load_size = read;
CloseHandle(h);
```

---

## 2. PBG4 封包访问

### 2.1 目录查找

```c
// pbg_find_size(name) - 返回解压后大小
entry = pbg_find_entry(name);
return entry ? entry->size : 0;
```

### 2.2 解压入口

```c
// pbg_read_entry(name, out)
entry = pbg_find_entry(name);
if (entry && verify_key(...)) {
    size = entry->end - entry->offset;      // +0x14 - +0x4
    tmp = GlobalAlloc(0, size);
    // 解密 + LZSS 解压
}
```

**条目结构**（与 `tools/pbg4.py` 独立逆向的结果一致）：

| 偏移 | 含义 |
|------|------|
| `+0x04` | 数据偏移 |
| `+0x08` | 解压后大小 |
| `+0x14` | 数据结束位置 |

---

## 3. 音频系统

### 3.1 初始化（snd_init）

```c
QueryPerformanceFrequency(&perf);      // 高精度计时器
device->Clear(0, NULL, D3DCLEAR_TARGET, 0xff000000, 1.0f, 0);
// bgm/init.mid + thbgm.fmt
```

### 3.2 音频文件格式支持

| 格式 | 处理函数 | 说明 |
|------|---------|------|
| **WAV** | `snd_parse_wav` | RIFF/WAVE 解析 → DirectSound 缓冲 |
| **MIDI** | `snd_midi_open` / `play` | WinMM MIDI 流 |
| **流式 BGM** | `bgm_stream_open` | `./thbgm.dat` 内嵌音频 |

### 3.3 WAV 解析（snd_parse_wav）

```c
if (strncmp(data, "RIFF", 4) != 0) return 0;
riff_size = *(u32*)(data + 4);
if (strncmp(data + 8, "WAVE", 4) != 0) return 0;

// 逐块查找
fmt_chunk  = snd_riff_find_chunk(data + 12, "fmt ", &size, ...);
data_chunk = snd_riff_find_chunk(data + 12, "data", &size, ...);
```

**标准 RIFF 解析**，可完全照抄。

### 3.4 流式播放

```c
// 每帧调用
snd_stream_service()
    ├── 检查缓冲状态
    ├── 填充/淡出
    └── 日志 "Sound : Fill Buffer Stage"
```

DirectSound 使用**通知回调**驱动：

```c
snd_wave_stream_cb()
    ├── Buffer->Lock()
    ├── 复制新数据
    └── Buffer->Unlock()
```

### 3.5 音效请求（snd_request）

```c
void snd_request(int group, int index)
{
    short v = table[0x49ea8e + index * 8];    // 每项 8 字节
    for (i = 0; i < 5; i++) {
        if (active[i] == index) return;       // 重复则跳过
        if (active[i] < 0) break;             // 找空槽
    }
    if (i < 5) {
        active[i] = index;
        group->buf[index] = v;
    }
}
```

**5 个并发槽位**，重复请求合并。

### 3.6 按名播放（snd_play_by_name）

```c
for (i = 0; i < 31; i++) {
    if (slot[i].ptr == 0) break;              // 找空槽
}
// 每槽 0x10c 字节
```

**31 个音效槽位。**

---

## 4. 音频资源清单（已从封包确认）

| 类型 | 数量 | 说明 |
|------|------|------|
| `.wav` | 30 | 音效 |
| `.mid` | 21 | BGM 曲目 |
| `.fmt` | 1 | `thbgm.fmt`（音轨表） |
| `bgm/init.mid` | 1 | 初始化音乐 |

**BGM 曲目命名**：`bgm/th07_NN.mid`（NN = 01..21）。

---

## 5. 日志系统

```c
dbg_log_append(buf, fmt, ...)     // sprintf 到 8196 字节缓冲
dbg_log_append_err(...)           // 错误流
dbg_logf_stub(...)                // 【空函数】发布版禁用
```

**重要**：`FUN_0045e4f0` 是**空函数** ——
说明发布版把 `%s Load ...` / `%s Decode ...` 日志全部编译掉了。
调试版可能保留。

---

## 6. 重制版照抄要点

### 6.1 必须保留

| 特性 | 原因 |
|------|------|
| 封包内只存文件名 | 影响资源查找逻辑 |
| `from_disk` 双路径 | 便于开发期直接读文件 |
| RIFF 块顺序容忍 | WAV 块顺序可能变化 |
| 5 槽音效合并 | 防止音效叠加爆音 |
| 1/16 跟随插值 | 手感 |

### 6.2 可以替换

| 原实现 | 建议 |
|--------|------|
| DirectSound | SDL3 Audio |
| WinMM MIDI | 内置 MIDI 合成器或音频文件替换 |
| `thbgm.dat` 流式 | 可直接用无损音频文件 |
| PBG4 封包 | 保留解包工具，运行时可用目录 |

### 6.3 音频混合器设计

TH07 的音频架构：

```
BGM 层 (MIDI 或 WAV 流)
  └── 流式缓冲（通知回调驱动）

SFX 层 (WAV)
  └── 31 个并发槽位
      └── 5 个请求合并槽
```

重制版建议保持**分层混合**，但用现代音频 API。

---

## 7. 待确认

- [ ] `thbgm.fmt` 的具体结构
- [ ] MIDI 通道与音色映射
- [ ] 音频总音量 / 独立音量控制
- [ ] `snd_stream_service` 的完整淡入淡出逻辑
