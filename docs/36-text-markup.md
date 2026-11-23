# 对话框文字渲染与内联标记语言

> 来源：`msg_text_render`（`FUN_0041d700`, 247 行）。
>
> **这是本轮最重要的发现**：TH07 的对话文字不是纯字符串，
> 而是**带内联指令的标记语言**，`@` 为前缀。

---

## 1. 渲染模型

```c
void msg_text_render(dialog *d)
{
    while (d->text_timer < 1) {
        switch (*d->text_ptr) {           // 读当前字符
        case 0: case 10: case 13:         // 结束/换行
            goto line_break;
        default:                          // 普通字符
            buffer[n++] = text_ptr[0];
            buffer[n++] = text_ptr[1];
            text_ptr += 2;                // 每字符 2 字节（SJIS）
            break;
        }
    }
}
```

**每字符 2 字节** = Shift-JIS 编码（日文）。

---

## 2. 内联标记（`@` 前缀）

> **重要修正**：我最初以为 `@` 标记是对话文本里普遍存在的语法。
> 用真实数据核对后，8 个 msg 文件里只有 12 处 `@@`，
> **没有任何 `@0`/`@F`/`@a` 等标记**。
>
> 说明：这些分支处理的是**剧本指令流中的控制字符**，
> 而正文（SJIS 日文）是普通字符走 default 分支。
> 标记可能只出现在特定脚本中，而非全部文件。

遇到 `@` 时读取下一个字符决定操作：

| 标记 | 参数 | 功能 |
|------|------|------|
| **`@0`** | — | 显示角色立绘 1 |
| **`@1`** | — | 显示角色立绘 2 |
| **`@2`** | — | 显示角色立绘 3 |
| **`@3`** | — | 显示角色立绘 4 |
| **`@F`** | — | 检查存档解锁（扫描 6×4 矩阵） |
| **`@R`** | — | 重置 16 个文字槽的状态 |
| **`@M`** | `<整数>` | 设置音乐/音效 |
| **`@V`** | `<a>/<b>` | 设置速度比率 `a/b` |
| **`@a`** | `<槽><脚本><精灵>` | 绑定 ANM 脚本与精灵 |
| **`@b`** | `<路径>` | **加载图片资源** |
| **`@c`** | `<整数>` | 设置某参数 |
| **`@m`** | `<文件名>` | **播放 BGM** |
| **`@r`** | `<次数><时长>` | 等待并循环 |

### 2.1 `@0`-`@3` 的实现

```c
case '@':
    text_ptr++;
    switch (*text_ptr) {
    case '0': case '1': case '2': case '3':
        text_ptr++;
        d->portrait_index = (c - '0') + 1;    // 1..4
        d->portrait_anim = 0;
        d->portrait_timer = text_read_int();  // 读后续整数
        break;
```

**所以 `@0120` 表示"显示立绘 1，持续 20 帧"。**

### 2.2 `@F` 的解锁检查

```c
case 'F':
    if (text_check_unlock(text_ptr + 1) != 0)
        return -1;                        // 失败

    // 扫描 6×4 存档矩阵
    for (row = 0; row < 6; row++)
        for (col = 0; col < 4; col++)
            if (save_matrix[col + row*0x1c] == 'c' ||
                save_matrix[col + row*0x1c + 6] == 'c')
                d->has_cleared = 1;

    // 注意：这里是 fallthrough 到 @R
case 'R':
    for (i = 0; i < 0x10; i++)
        text_slot[i].state = 0;
    break;
```

**`@F` 会 fallthrough 到 `@R`**（代码里没有 break），
所以执行 `@F` 后所有文字槽都会被重置。

### 2.3 `@a` 绑定动画

```c
case 'a':
    slot   = text_read_int();
    script = text_read_int();
    sprite = text_read_int();
    anm_set_sprite_script(text_slot[slot], script + 0x600);
    anm_bind_sprite(text_slot[slot], sprite + 0x600);
    break;
```

### 2.4 `@r` 等待循环

```c
case 'r':
    lines = text_read_int();
    frames = text_read_int();
    d->line_count = lines;
    d->frame_timer = frames;

    // 跳到行尾
    while (*text_ptr != '\n' && *text_ptr != '\r')
        text_ptr++;
    break;
```

---

## 3. 文字槽结构

| 偏移 | 含义 |
|------|------|
| `+0x252C` | 当前文本指针 |
| `+0x2528` | 立绘索引（1-4） |
| `+0x2520` | 立绘动画帧 |
| `+0x2524` | 立绘计时 |
| `+0x2518` | `@c` 设置的值 |
| `+0x24FC` | 等待计数器 |
| `+0x2500` | 等待总时长 |
| `+0x24D8` | 已通关标志 |
| `+0x14 + i*0x24C` | 16 个文字槽的 AnmInstance |

---

## 4. 存档矩阵（关键数据）

```c
g_save_matrix  // 6 行 × 4 列，步长 0x1c
```

| 维度 | 含义 |
|------|------|
| 6 行 | 6 个存档槽 |
| 4 列 + 偏移 6 | 每槽 4+4 个标记 |

标记值为 `'c'`（99）= **已通关**。

> 这与前面 `extra_unlocked_a` / `extra_unlock_check` 发现的
> `99` 标记是同一套机制，两处独立佐证。

---

## 5. 重制版照抄要点

### 5.1 必须保留

| 特性 | 原因 |
|------|------|
| `@` 标记语法 | 剧本数据依赖它 |
| SJIS 双字节字符 | 日文显示 |
| `@F` fallthrough 到 `@R` | 解锁检查同时重置 |
| `@0`-`@3` 的 `索引+1` | 立绘槽位映射 |

### 5.2 建议改进

| 原实现 | 建议 |
|--------|------|
| 固定 SJIS | 改为 UTF-8，内部转码 |
| `@F` 隐式 fallthrough | 显式写清楚（易误读） |
| 单字节 `@c` 参数 | 保留但文档化 |

---

## 6. 文字内容（已确认位置）

msg 文件中的正文是 **Shift-JIS 日文**，实测样本：

```
msg1.dat: レイ・ホワイトロック      （灵梦的日文名）
msg3.dat: アリス・マーガトロイド    （爱丽丝）
msg4.dat: 　　 博麗 トランペッター　
```

- 每字符 **2 字节**
- `0x8140` = 全角空格
- 与渲染代码的「每字符读 2 字节」完全一致

## 7. 待确认

- [ ] `@c` 参数的具体用途
- [ ] `@M` 与 `@m` 的区别（M 是音效，m 是 BGM？）
- [ ] 文字内容在 msg 文件中的组织方式
- [ ] 立绘索引 1-4 与 `.sht` 角色的对应
