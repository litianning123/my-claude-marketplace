# my-claude-marketplace

[English](README.md)

[Claude Code](https://claude.com/claude-code) **插件**集合 — 每个插件提供一个技能（skill），为 Claude 扩展专门的、可重复执行的工作流。

每个插件包含一个 `.claude-plugin/plugin.json` 清单文件和一个 `skills/<name>/SKILL.md` 文件，后者是技能激活后 Claude 的操作指令。辅助脚本位于 `<plugin>/scripts/` 目录下。不依赖构建系统或第三方库 —— 技能由 Markdown 文件加纯标准库 Python 脚本构成。

## 插件列表

| 技能 | 功能 |
|-------|--------------|
| [`hook-doctor`](hook-doctor/) | 检查和修复 Claude Code hook 配置。检测 7 种常见配置错误（未加引号的路径变量、缺失/不可执行的脚本、未知事件、无效 JSON、缺失 command 字段、已弃用语法），并对其中 2 种可自动修复的问题应用安全、幂等的修复。 |
| [`efficiency-audit`](efficiency-audit/) | 分析 Claude Code 对话记录，发现重复出现的低效模式 — 反复修正、上下文缺失、启动缓慢、可自动化场景、git 工作流错误、工具调用失败和 hook 错误 — 然后通过启发式规则引擎生成修复建议，并以幂等标记块的形式应用到 CLAUDE.md 中。 |
| [`quicknotes`](quicknotes/) | 快速、零子进程的便签记录和管理。Agent 直接使用内置工具（Write、Read、Bash、Grep、Edit）操作文件 — 无 Python 开销。支持记录、列表、搜索、查看、完成、更新、到期提醒、当前项目查看和引用（双向链接）。便签是以 JSON frontmatter 格式存储的中心化 Markdown 文件。 |
| [`dev-unslop`](dev-unslop/) | 清除技术文档中的 AI 水话（slop）——README、PR 回复、代码注释、文档。检测清嗓子式开场、空洞形容词、结构性臃肿、AI 水印词（30+ 中英文）和 PR 过度客套。遵循资深工程师的文字审美：不承载信息的句子一律删除。 |
| [`loop-creator`](loop-creator/) | 向导式对话，生成可直接运行的 `/loop` 配置。可从对话历史中发现循环候选任务（重复提示、时间线索），然后输出命令、项目文件夹或可复用技能。内置循环工程最佳实践：就绪关卡、权限阶梯、制作-检查验证和先手动后自动原则。 |

## 开发

不依赖构建系统或第三方库。带有测试的脚本使用 Python 标准库 `unittest`，从脚本所在目录运行：

```bash
# hook-doctor
cd hook-doctor/scripts && python3 -m unittest test_doctor -v

# efficiency-audit
cd efficiency-audit/scripts && python3 -m unittest test_audit -v

# loop-creator
cd loop-creator/scripts && python3 -m unittest discover -q -v
```

## 添加新插件

1. 创建以 kebab-case 命名的顶级目录（与插件名称一致）。
2. 添加 `.claude-plugin/plugin.json`，包含 `name` 和 `description`。
3. 添加 `skills/<name>/SKILL.md` 作为 agent 执行流程。在 frontmatter 的 `description` 字段中前置触发短语 — 这是决定是否激活技能时唯一被读取的文本。通过 `${CLAUDE_PLUGIN_ROOT}/scripts/...` 引用辅助脚本（运行时动态解析）。
4. 将辅助代码放在 `<plugin>/scripts/` 下。
5. 在 `.claude-plugin/marketplace.json` 中注册插件 — 在 `plugins` 数组中添加条目，包含 `name`、`source`、`description`、`version`、`homepage` 和 `repository`。
6. 在上方表格中添加插件。

## 许可证

MIT
