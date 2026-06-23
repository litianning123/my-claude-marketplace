---
name: hook-doctor
description: "Inspects and repairs Claude Code hook configurations — plugin hooks.json and project/user settings.json. Use when a hook is failing or misconfigured, when an efficiency audit reports hook_errors, or when the user asks to check, diagnose, or fix hooks. Detects unquoted ${CLAUDE_PLUGIN_ROOT}/${CLAUDE_PROJECT_DIR} commands that fail in agent-mode (exit 127, '/bin/sh: .../Library/Application: No such file'), missing/non-executable scripts, unknown events, invalid JSON, missing command fields, and deprecated single-command syntax. Trigger phrases: 'fix my hooks', 'hook is broken', 'why did my hook fail', 'check my plugin hooks', 'diagnose hook errors', 'hook exit 127'."
---

# Hook Doctor

Diagnose and repair Claude Code hook configurations. Static analysis only — no hooks are executed.

## 0. Intent

Ask before scanning:
> "Diagnose-only, or apply fixes if found? All hooks or a specific plugin?"

## 1. Scan

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/hook-doctor/*/ 2>/dev/null | head -1)
python3 "${PLUGIN_ROOT}/scripts/doctor.py" [--project DIR] [--root DIR]
```

Group findings by file. Flag fixable vs. report-only clearly.

## 2. Decide

For each fixable finding, state the blast radius (installed plugin file vs. user settings) and offer:
- **(a)** fix locally
- **(b)** upstream PR
- **(c)** both
- **(d)** skip

Never edit without explicit choice. Show the exact change before applying.

## 3. Apply & Verify

```bash
python3 "${PLUGIN_ROOT}/scripts/doctor.py" --apply [same flags as scan]
```

Re-scan to confirm findings are resolved. If the fixed file is in a git repo, show `git diff`.

## Checks Reference

| Check | Problem | Fixable? |
|-------|---------|----------|
| `invalid_json` | File doesn't parse as JSON | No |
| `unknown_event` | Event name not recognized | No |
| `no_command` | Command handler missing command string | No |
| `unquoted_var` | `${CLAUDE_*}` path unquoted (breaks agent-mode) | **Yes** |
| `script_missing` | Referenced script doesn't exist | No |
| `not_executable` | Bare-path script lacks execute bit | **Yes** |
| `deprecated_syntax` | Single `command` instead of `commands` array | No |
