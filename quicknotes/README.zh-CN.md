# Quicknotes

[English](README.md)

为 Claude Code 打造的快速、零子进程便签记录和管理工具。

## 为什么重写

[原始 quicknotes 插件](https://github.com/litianningdatadog/claude-marketplace/tree/main/quicknotes) 每次操作都会启动 Python — `python3 scripts/qn.py capture "text"` — 每次调用都需要承担 Python VM 启动 + 导入的开销（约 300-500ms）。此版本消除了所有 Python 子进程：Claude Code agent 使用其已在运行的内置工具（Write、Read、Bash、Grep、Edit）直接操作便签文件。功能相同，存储格式相同，**快 10 倍**。

## 快速开始

### 记录便签
```
/qn 买牛奶和鸡蛋 #购物
```
→ `✓ 已记录 [a1b2] "买牛奶和鸡蛋"  标签: 购物`

### 列出便签
```
/qn list
```

### 搜索便签
```
/qn search 牛奶
```

### 查看便签
```
/qn show a1b2
```

### 完成便签
```
/qn done a1b2
```

### 过期便签
```
/qn due
```

### 当前项目便签
```
/qn here
```

## 操作

| 命令 | 说明 |
|---------|-------------|
| `qn <文本> [#标签]` | 记录便签（默认） |
| `qn list [--project P] [--tag T]` | 列出所有便签 |
| `qn search <查询>` | 在标题/正文/标签中模糊搜索 |
| `qn show <id\|模糊匹配>` | 完整元数据、正文和引用 |
| `qn done <id\|模糊匹配>` | 完成 — 删除便签 |
| `qn update <id\|模糊匹配> [参数]` | 编辑标题、标签、优先级、到期日、正文 |
| `qn due` | 已过期的便签 |
| `qn here` | 当前项目/目录的便签 |
| `qn ref <a> <b>` | 双向链接两个便签 |

## 自然语言触发

当你这样说时技能会自动激活：
- "记一下：..."
- "提醒自己：..."
- "提醒我..."
- "写个便签..."
- "我有哪些便签？"
- "列出我的便签"
- "标记便签为完成"

## 会话提醒（可选）

启用会话开始时的主动提醒。技能会在安装前征得你的同意 — 批准后你会看到：

```
📝 quicknotes: 3 个已过期，2 个当前项目待办  （运行 `qn due` / `qn here`）
   • 过期：买牛奶
   • 过期：审查季度预算
```

没有待办事项时静默。

## Shell 别名（可选）

在 Claude Code 外部使用：
```bash
bash scripts/install_alias.sh
```
为你的 shell RC 添加 `qn()` 函数。之后在任何终端中都可以使用 `qn 买牛奶 #购物`。

## 存储

便签存储在 `~/.quicknotes/notes/<id>.md`，以带 JSON frontmatter 的 Markdown 文件形式存在。你可以直接阅读、编辑或版本控制它们。

```
~/.quicknotes/
└── notes/
    ├── 20260628-143022-a1b2.md
    ├── 20260627-090000-cc33.md
    └── ...
```

格式与原始基于 Python 的 quicknotes 插件 100% 兼容。

## 架构

核心操作无需 Python 脚本。Claude Code agent 直接使用其内置工具：
- **Write** — 创建便签文件
- **Read** — 读取便签内容
- **Bash** — 快速元数据查询（日期、git 信息、列表）
- **Grep** — 搜索便签
- **Edit** — 更新便签字段

完整技术细节见 `references/tech-doc.md`。

## 对比

| | 原始版（Python） | 本版本 |
|---|---|---|
| 记录耗时 | ~350-500ms | ~50ms |
| Python 依赖 | 必需 | 无需 |
| 每次操作需子进程 | 是（python3） | 否（仅元数据使用 bash） |
| 存储格式 | `~/.quicknotes/notes/*.md` | 相同 — 100% 兼容 |

## 许可证

MIT
