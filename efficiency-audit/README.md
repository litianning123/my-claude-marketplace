# efficiency-audit

Analyzes recent Claude Code conversation transcripts to surface recurring inefficiencies — repeated corrections, missing context, slow session starts, automation candidates, git workflow errors, tool failures, and hook errors — then generates fix recommendations via a heuristic rule engine and applies them as idempotent marker blocks in CLAUDE.md.

> **Canonical behavior lives in [`SKILL.md`](skills/efficiency-audit/SKILL.md).** This README covers human-facing install, CLI usage, and testing.

## How it works

Pipeline: scan transcripts → **filter noise** (7 categories) → score messages with regex patterns → group by friction category → generate recommendations via heuristic templates → **route to correct CLAUDE.md with data-driven scope analysis** → report → apply with SOSA™ approval.

**No LLM dependency.** Rule generation uses templated heuristics keyed to pattern categories. Templates are editable in `references/rule-templates.json`.

**Noise filtering.** System-generated boilerplate (context-compaction messages, command tags, security review injections, pasted tool output) is stripped before analysis — see `references/noise-filters.md` for the full filter catalog.

**Intelligent routing.** `router.py` resolves each recommendation using project-distribution counting (3+ projects → global, ≥70% concentration → project), generates structured A/B prompts when both files exist, and annotates checklist entries with `(global → ~/.claude/CLAUDE.md)` or `(project: repo → .claude/CLAUDE.md)`. Settings.json and hook-doctor targets are excluded from CLAUDE.md routing.

**Bloat remediation.** When a CLAUDE.md exceeds 200 lines, the `references/recipe-book.md` procedure extracts domain-scoped rules into `.claude/rules/<name>.md` files with `paths:` frontmatter before new rules are added.

## Install

```
/plugin marketplace add <your-marketplace>
/plugin install efficiency-audit@<your-marketplace>
```

## Running directly

```bash
# Standard audit, last 30 days
python3 scripts/audit.py

# Specific project, text output
python3 scripts/audit.py --project my-repo --output text

# JSON output for programmatic consumption
python3 scripts/audit.py --output json

# Apply recommendations to CLAUDE.md
python3 scripts/audit.py --apply
```

| Flag | Meaning |
|------|---------|
| `--days N` | Scan last N days (default: 30) |
| `--project P` | Restrict to project matching P |
| `--output json\|text` | Output format (default: text) |
| `--apply` | Write approved rules to target files |

## Files

```
efficiency-audit/
├── .claude-plugin/plugin.json
├── skills/efficiency-audit/SKILL.md
├── README.md
├── references/
│   ├── category-guide.md       # Phase 2 pattern interpretation + thresholds
│   ├── governance.md           # SOSA™ approval rules
│   ├── karpathy-guardrails.md  # Phase 5 opt-in guardrails merge
│   ├── noise-filters.md        # 7 false-positive filter categories
│   ├── recipe-book.md          # CLAUDE.md bloat remediation + stacked PR procedure
│   └── rule-templates.json     # Heuristic rule templates (editable)
└── scripts/
    ├── audit.py                # CLI entry point
    ├── scanner.py              # Transcript parser + noise filter + tool error classifier
    ├── patterns.py             # Regex matching engine + baseline tracking
    ├── synthesizer.py          # Heuristic recommendation generator
    ├── router.py               # Data-driven CLAUDE.md routing + A/B prompts
    ├── applier.py              # Idempotent marker-block writer
    ├── scorer.py               # Piecewise-linear file bloat scorer
    └── test_audit.py           # Unittest suite (40 tests)
```
