# hook-doctor — Design Spec

**Date:** 2026-06-22
**Status:** approved

## Overview

A Claude Code plugin that performs static analysis on installed hook configurations, detects 7 common misconfiguration patterns, and applies targeted fixes for the 2 auto-fixable ones. All checks are static — no hooks are executed.

## Architecture

4 self-contained modules, each with one responsibility:

```
hook-doctor/
├── .claude-plugin/plugin.json     # {"name": "hook-doctor", ...}
├── skills/hook-doctor/SKILL.md    # Agent procedure (4-phase)
├── README.md                      # Human-facing docs
└── scripts/
    ├── doctor.py                  # CLI entrypoint + orchestration
    ├── sources.py                 # Hook source discovery
    ├── checks.py                  # Check protocol, registry, 7 checks
    ├── fixer.py                   # Fix application
    └── test_doctor.py             # Test suite (unittest)
```

**Dependencies:** Python 3.10+, stdlib only. No third-party packages.

## Module Design

### sources.py — Hook Source Discovery

Finds all hook config files on the system:

| Source | Location | Method |
|--------|----------|--------|
| Plugin hooks | `~/.claude/plugins/` | Walk tree for `hooks/hooks.json`, dedup by realpath |
| User settings | `~/.claude/settings.json` + `.local.json` | Direct existence check |
| Project settings | `<project>/.claude/settings.json` + `.local.json` | Direct existence check |

Exposes: `discover_sources(project_dir: Path) -> list[HookSource]`

Gracefully handles missing directories (returns empty list, doesn't crash).

### checks.py — Check Protocol, Registry, and 7 Checks

**Data model:**

```python
@dataclass
class Finding:
    file: str          # Absolute path to config file
    event: str | None  # Hook event name, None for file-level errors
    command: str | None  # Raw command string, None for structural errors
    check: str         # Check slug
    detail: str        # Human-readable explanation
    fixable: bool      # Can be auto-repaired?
```

**Check protocol:** Each check is a `Callable[[dict, CheckContext], Finding | None]`. Returns a Finding when a problem is detected, None otherwise.

**Registry:** `ALL_CHECKS: list[Check]` — adding a check means writing one function and appending to this list. The orchestrator never changes.

**The 7 checks:**

| # | Slug | What it detects | Fixable? |
|---|------|----------------|----------|
| 1 | `invalid_json` | File doesn't parse as JSON | No |
| 2 | `unknown_event` | Event name not in recognized Claude Code event set | No |
| 3 | `no_command` | Handler type is "command" but has no command string | No |
| 4 | `unquoted_var` | `${CLAUDE_PLUGIN_ROOT}` (or PROJECT_DIR, PLUGIN_DATA) unquoted in command | **Yes** |
| 5 | `script_missing` | Resolved script path doesn't exist on disk | No |
| 6 | `not_executable` | Bare-path script (no interpreter prefix) lacks execute bit | **Yes** |
| 7 | `deprecated_syntax` | Handler uses single `"command"` string where `"commands"` array is available | No |

Path resolution for checks 5–6 uses confinement: paths escaping the plugin root via `../` are rejected.

### fixer.py — Fix Application

Two fix functions, both safety-gated:

**`fix_unquoted_vars(file_path: Path) -> int`**
- Walks every handler's command field in the JSON
- Wraps unquoted `${CLAUDE_PLUGIN_ROOT}/...` tokens in double quotes via regex
- Already-quoted tokens are skipped (idempotent)
- Re-validates JSON before writing — parse failure → no write
- Returns count of commands fixed

**`fix_executable(finding: Finding) -> bool`**
- Extracts resolved script path from the finding
- Before `chmod`: re-checks file exists, is not a symlink (TOCTOU guard), is a regular file
- Adds owner/group/other execute bits
- Returns success/failure

Safety invariants:
1. Validate-before-write (parse modified JSON before touching disk)
2. Symlink refusal (`chmod` won't follow symlinks)
3. Path already confined at scan time — fixer only receives verified paths
4. Idempotent (`--apply` twice on fixed file = no-op)

### doctor.py — CLI & Orchestration

Thin layer using argparse. Three flags:

```
--project DIR    Project to inspect (default: cwd)
--root DIR       Scan only this plugin tree (skip settings.json)
--apply          Write fixes (without this, report only)
```

Flow:
1. `discover_sources(project)` → `list[HookSource]`
2. For each source: parse JSON, iterate handlers, run `ALL_CHECKS`
3. Group `Finding` objects by file
4. Print report: file path, then each finding with `[slug]` tag and detail
5. If `--apply`: run fixer on fixable findings
6. Re-scan fixed files to confirm resolution
7. Print summary: `N fixed, M remaining (report-only)`

## Testing

Single test file (`test_doctor.py`), stdlib `unittest`. Tests create temp plugin trees with synthetic `hooks.json` using `tempfile.mkdtemp` — real filesystem, no mocking.

Categories:
- **Per-check tests:** Each check's detection/ignore behavior
- **Fixer tests:** Rewrite correctness, idempotency, symlink refusal
- **Integration:** Full doctor.py flow against temp tree with multiple issues
- **Edge cases:** Malformed JSON, empty hooks, missing dirs, `../` traversal

## SKILL.md — Agent Procedure

4 phases, kept concise:

0. **Intent** — "Diagnose-only or apply fixes?"
1. **Scan** — Run `doctor.py`, present findings grouped by file
2. **Decide** — For each fixable finding: fix locally / upstream PR / both / skip
3. **Apply & Verify** — Run `doctor.py --apply`, re-scan, show diff

## Non-Goals

- No hook execution (static analysis only)
- No new hook authoring (that's `hookify`'s domain)
- No `settings.json` structure editing (that's `update-config`'s domain)
- No network calls, no telemetry, no config file
