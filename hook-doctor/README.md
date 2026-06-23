# hook-doctor

Inspects and repairs **Claude Code plugin hook configurations** — the `hooks/hooks.json`
files under `~/.claude/plugins/` and user/project `settings.json`. Scans every installed
plugin for known hook-config problems, reports them, and (with explicit opt-in) applies
safe, idempotent fixes.

> **Canonical behavior lives in [`SKILL.md`](skills/hook-doctor/SKILL.md).** This README covers
> human-facing install, direct CLI usage, and testing. If the two disagree, `SKILL.md` wins.

## What it checks

All checks are **static** (no hooks are run). 7 checks total, 2 auto-fixable.

| Check | Problem | Fix |
|-------|---------|-----|
| `unquoted_var` | `${CLAUDE_PLUGIN_ROOT}` unquoted — breaks in agent-mode where paths contain spaces | Fixable — wrap the token in double quotes |
| `not_executable` | Bare-path script lacks execute bit | Fixable — `chmod +x` (with symlink guard) |
| `script_missing` | Referenced script doesn't exist on disk | Report-only |
| `unknown_event` | Event name not recognized — hook never fires | Report-only |
| `no_command` | `type: "command"` handler has no `command` string | Report-only |
| `invalid_json` | File doesn't parse as JSON | Report-only |
| `deprecated_syntax` | Single `command` string where `commands` array is available | Report-only |

## Install

```
/plugin marketplace add <your-marketplace>
/plugin install hook-doctor@<your-marketplace>
```

## Running directly

```bash
# Inspect effective hooks for the current project
python3 scripts/doctor.py

# Inspect a specific project
python3 scripts/doctor.py --project /path/to/repo

# Scan only a plugin tree
python3 scripts/doctor.py --root ~/.claude/plugins/marketplaces/some-marketplace

# Apply fixes
python3 scripts/doctor.py --apply
```

| Flag | Meaning |
|------|---------|
| `--project DIR` | Project to inspect (default: cwd) |
| `--root DIR` | Scan only this tree (skips settings.json) |
| `--apply` | Write fixes (without it, report only) |

## Tests

Standard-library `unittest`, no dependencies:

```bash
cd scripts && python3 -m unittest test_doctor -v
```

## Files

```
hook-doctor/
├── .claude-plugin/plugin.json       # Plugin manifest
├── skills/hook-doctor/SKILL.md      # Agent procedure (4-phase)
├── README.md                        # This file
└── scripts/
    ├── doctor.py                    # CLI entrypoint + orchestration
    ├── sources.py                   # Hook source discovery
    ├── checks.py                    # Check protocol, registry, 7 checks
    ├── fixer.py                     # Fix application
    └── test_doctor.py               # Test suite (unittest)
```
