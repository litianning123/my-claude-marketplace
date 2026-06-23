---
name: efficiency-audit
description: "Analyzes recent Claude Code conversation transcripts to surface recurring inefficiencies — repeated corrections, missing context, slow starts, automation candidates, git workflow errors, tool failures, and hook errors — then generates fix recommendations and applies them as idempotent marker blocks in CLAUDE.md. Use when the user wants to improve their workflow, reduce repeated corrections, eliminate missing-context frustration, fix git workflow anti-patterns, or automate recurring patterns. Trigger phrases: 'improve my workflow', 'audit my usage', 'what am I repeating', 'efficiency audit', 'review my conversations', or any request to update CLAUDE.md based on observed patterns."
---

# Efficiency Audit

Analyze Claude Code transcripts to find and fix workflow inefficiencies. All analysis is read-only — no transcript files are modified.

## 0. Intent

Ask: "Standard audit or specific areas to focus on?"

## 1. Scan

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/efficiency-audit/*/ 2>/dev/null | head -1)
python3 "${PLUGIN_ROOT}/scripts/audit.py" --days 30 [--project NAME]
```

Reports findings in 5 categories: corrections, missing context, slow starts, automation candidates, git workflow errors. Also surfaces tool failures and hook errors.

## 2. Report

Present recommendations ordered by impact. For each: rule text, evidence, target file, estimated tokens saved. Mark confidence (high/medium/low). User approves or skips each rule individually.

## 3. Apply

For approved rules, apply one at a time via Plan → Act → Verify (SOSA™ governance):
1. Show exact diff
2. Wait for explicit confirmation
3. Write to target file
4. Verify the change

```bash
python3 "${PLUGIN_ROOT}/scripts/audit.py" --apply
```

## Categories Reference

| Category | What it detects | Threshold |
|----------|----------------|-----------|
| corrections | User redirects Claude | count ≥ 3 |
| missing_context | Re-explained stable facts | sessions ≥ 3 |
| slow_start_context | Per-session orientation | sessions ≥ 2 |
| automation_candidates | Recurring procedural intent | count ≥ 2 |
| git_workflow_errors | Stale refs, bad cascades | count ≥ 2 |
| hook_errors | Failing hook configs | Any — route to hook-doctor |
