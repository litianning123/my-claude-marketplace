# hook-doctor

[English](README.md)

检查和修复 **Claude Code 插件 hook 配置** — `~/.claude/plugins/` 下的 `hooks/hooks.json` 文件以及用户/项目的 `settings.json`。扫描每个已安装的插件，查找已知的 hook 配置问题，报告问题，并（在明确选择后）应用安全、幂等的修复。

> **行为规范定义在 [`SKILL.md`](skills/hook-doctor/SKILL.md) 中。** 本 README 面向人工阅读，涵盖安装、直接 CLI 使用和测试。若两者有冲突，以 `SKILL.md` 为准。

## 检查项

所有检查均为**静态**（不实际运行 hook）。共 7 项检查，其中 2 项可自动修复。

| 检查项 | 问题 | 修复 |
|-------|---------|-----|
| `unquoted_var` | `${CLAUDE_PLUGIN_ROOT}` 未加引号 — 在 agent 模式下路径包含空格时会中断 | 可修复 — 用双引号包裹该标记 |
| `not_executable` | 裸路径脚本缺少执行权限 | 可修复 — `chmod +x`（带符号链接保护） |
| `script_missing` | 引用的脚本在磁盘上不存在 | 仅报告 |
| `unknown_event` | 事件名称无法识别 — hook 永远不会触发 | 仅报告 |
| `no_command` | `type: "command"` 的处理器缺少 `command` 字符串 | 仅报告 |
| `invalid_json` | 文件无法解析为 JSON | 仅报告 |
| `deprecated_syntax` | 存在 `commands` 数组可用的情况下使用了单个 `command` 字符串 | 仅报告 |

## 安装

```
/plugin marketplace add <your-marketplace>
/plugin install hook-doctor@<your-marketplace>
```

## 直接运行

```bash
# 检查当前项目的有效 hook
python3 scripts/doctor.py

# 检查指定项目
python3 scripts/doctor.py --project /path/to/repo

# 仅扫描插件目录树
python3 scripts/doctor.py --root ~/.claude/plugins/marketplaces/some-marketplace

# 应用修复
python3 scripts/doctor.py --apply
```

| 参数 | 含义 |
|------|------|
| `--project DIR` | 要检查的项目（默认：当前目录） |
| `--root DIR` | 仅扫描此目录树（跳过 settings.json） |
| `--apply` | 写入修复（不加则仅报告） |

## 测试

标准库 `unittest`，无外部依赖：

```bash
cd scripts && python3 -m unittest test_doctor -v
```

## 文件结构

```
hook-doctor/
├── .claude-plugin/plugin.json       # 插件清单
├── skills/hook-doctor/SKILL.md      # Agent 执行流程（4 阶段）
├── README.md                        # 本文件
└── scripts/
    ├── doctor.py                    # CLI 入口 + 编排
    ├── sources.py                   # Hook 源发现
    ├── checks.py                    # 检查协议、注册表、7 项检查
    ├── fixer.py                     # 修复应用
    └── test_doctor.py               # 测试套件（unittest）
```
