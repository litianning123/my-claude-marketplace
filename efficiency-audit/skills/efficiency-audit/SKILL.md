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

## 2. Route

The audit output includes a routing table showing where each rule should go. Detect which CLAUDE.md files exist first:

```bash
[ -f ~/.claude/CLAUDE.md ] && echo "global: yes" || echo "global: no"
[ -f .claude/CLAUDE.md ]   && echo "project (.claude/): yes" || echo "project (.claude/): no"
[ -f CLAUDE.md ]           && echo "project (root): yes"     || echo "project (root): no"
```

Routing rules:
- **Only one file exists** → route there silently, no prompt needed
- **Both global and project files exist** → show an A/B prompt and wait for the user to choose
- **Neither exists** → ask which to create before proceeding
- **Project-specific rules** (all matches in one project) → route to project file
- **Cross-project rules** (seen across 3+ projects) → recommend global, but confirm before writing
- **Writing to `~/.claude/CLAUDE.md` affects every future session across all projects** — require explicit consent

## 3. Report

Present recommendations ordered by impact. For each: rule text, evidence, routed target file, estimated tokens saved. Mark confidence (high/medium/low). User approves or skips each rule individually.

## 4. Apply

For approved rules, apply one at a time via Plan → Act → Verify (SOSA™ governance):
1. Show exact diff
2. Wait for explicit confirmation
3. Write to target file
4. Verify the change

```bash
python3 "${PLUGIN_ROOT}/scripts/audit.py" --apply
```

## 5. Karpathy Guardrails (opt-in)

After applying rules, scan `corrections` and `missing_context` examples for behavioral anti-patterns. See `references/karpathy-guardrails.md` for signal keywords, thresholds, and merge procedure.

- Evidence threshold: ≥ 2 hits across all finding groups
- Offer once per audit — if declined, do not re-offer
- Merge is governed by the same SOSA rules as Phase 4

## Categories Reference

| Category | What it detects | Threshold |
|----------|----------------|-----------|
| corrections | User redirects Claude | count ≥ 3 |
| missing_context | Re-explained stable facts | sessions ≥ 3 |
| slow_start_context | Per-session orientation | sessions ≥ 2 |
| automation_candidates | Recurring procedural intent | count ≥ 2 |
| git_workflow_errors | Stale refs, bad cascades | count ≥ 2 |
| hook_errors | Failing hook configs | Any — route to hook-doctor |
