# efficiency-audit

Analyzes recent Claude Code conversation transcripts to surface recurring inefficiencies — repeated corrections, missing context, slow session starts, automation candidates, git workflow errors, tool failures, and hook errors — then generates fix recommendations via a heuristic rule engine and applies them as idempotent marker blocks in CLAUDE.md.

> **Canonical behavior lives in [`SKILL.md`](skills/efficiency-audit/SKILL.md).** This README covers human-facing install, CLI usage, and testing.

## How it works

Pipeline: scan transcripts → score messages with regex patterns → group by friction category → generate recommendations via heuristic templates → report → apply with approval.

**No LLM dependency.** Rule generation uses templated heuristics keyed to pattern categories. Templates are editable in `references/rule-templates.md`.

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
│   ├── category-guide.md
│   ├── governance.md
│   └── rule-templates.md
└── scripts/
    ├── audit.py
    ├── scanner.py
    ├── patterns.py
    ├── synthesizer.py
    ├── applier.py
    ├── scorer.py
    └── test_audit.py
```
