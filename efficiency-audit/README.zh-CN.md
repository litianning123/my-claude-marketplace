# efficiency-audit

[English](README.md)

分析近期 Claude Code 对话记录，发现重复出现的低效模式 — 反复修正、上下文缺失、会话启动缓慢、可自动化场景、git 工作流错误、工具调用失败和 hook 错误 — 然后通过启发式规则引擎生成修复建议，并以幂等标记块的形式应用到 CLAUDE.md 中。

> **行为规范定义在 [`SKILL.md`](skills/efficiency-audit/SKILL.md) 中。** 本 README 面向人工阅读，涵盖安装、CLI 使用和测试。

## 工作原理

流水线：扫描对话记录 → **过滤噪声**（7 个类别）→ 用正则模式对消息评分 → 按摩擦类别分组 → 通过启发式模板生成建议 → **通过数据驱动的作用域分析将规则路由到正确的 CLAUDE.md** → 报告 → 使用 SOSA™ 审批方式应用。

**不依赖 LLM。** 规则生成使用与模式类别关联的模板化启发式规则。模板可在 `references/rule-templates.json` 中编辑。

**噪声过滤。** 系统生成的样板内容（上下文压缩消息、命令标签、安全审查注入、粘贴的工具输出）在分析前被剔除 — 详见 `references/noise-filters.md` 中的完整过滤目录。

**智能路由。** `router.py` 通过项目分布统计（3 个及以上项目 → 全局，≥70% 集中在单个项目 → 项目级）来解析每条建议的目标文件，当两个文件同时存在时生成结构化的 A/B 提示，并为检查清单条目标注 `(global → ~/.claude/CLAUDE.md)` 或 `(project: repo → .claude/CLAUDE.md)`。settings.json 和 hook-doctor 的目标文件不参与 CLAUDE.md 路由。

**臃肿治理。** 当 CLAUDE.md 超过 200 行时，`references/recipe-book.md` 中的流程会在添加新规则之前，将按域划分的规则提取到带有 `paths:` frontmatter 的 `.claude/rules/<name>.md` 文件中。

## 安装

```
/plugin marketplace add <your-marketplace>
/plugin install efficiency-audit@<your-marketplace>
```

## 直接运行

```bash
# 标准审计，最近 30 天
python3 scripts/audit.py

# 指定项目，文本输出
python3 scripts/audit.py --project my-repo --output text

# JSON 输出，供程序化消费
python3 scripts/audit.py --output json

# 应用建议到 CLAUDE.md
python3 scripts/audit.py --apply
```

| 参数 | 含义 |
|------|------|
| `--days N` | 扫描最近 N 天（默认：30） |
| `--project P` | 仅限匹配 P 的项目 |
| `--output json\|text` | 输出格式（默认：text） |
| `--apply` | 将已批准的规则写入目标文件 |

## 文件结构

```
efficiency-audit/
├── .claude-plugin/plugin.json
├── skills/efficiency-audit/SKILL.md
├── README.md
├── references/
│   ├── category-guide.md       # 阶段 2 模式解读 + 阈值
│   ├── governance.md           # SOSA™ 审批规则
│   ├── karpathy-guardrails.md  # 阶段 5 可选护栏合并
│   ├── noise-filters.md        # 7 个误报过滤类别
│   ├── recipe-book.md          # CLAUDE.md 臃肿治理 + 堆叠 PR 流程
│   └── rule-templates.json     # 启发式规则模板（可编辑）
└── scripts/
    ├── audit.py                # CLI 入口
    ├── scanner.py              # 对话记录解析器 + 噪声过滤器 + 工具错误分类器
    ├── patterns.py             # 正则匹配引擎 + 基线追踪
    ├── synthesizer.py          # 启发式建议生成器
    ├── router.py               # 数据驱动的 CLAUDE.md 路由 + A/B 提示
    ├── applier.py              # 幂等标记块写入器
    ├── scorer.py               # 分段线性文件臃肿评分器
    └── test_audit.py           # 单元测试套件（40 个测试）
```
