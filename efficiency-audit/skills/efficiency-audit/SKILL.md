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

Noise is filtered automatically during parsing (see `references/noise-filters.md` for the 7 filter categories). If you see false positives in the report, the filter list is where to fix them — not by hand-editing findings.

## 2. Route

`router.py` resolves each recommendation to the right CLAUDE.md file using data-driven scope analysis:

- **Detects file presence** — checks `~/.claude/CLAUDE.md`, `.claude/CLAUDE.md`, root `CLAUDE.md`
- **Counts project distribution** — extracts which projects each pattern appears in from raw findings
- **Applies concentration thresholds** — 3+ distinct projects → global; ≥70% in one repo → project; 2–3 projects, no dominant → weak recommendation
- **Excludes non-CLAUDE.md targets** — settings.json → hookify:configure; hook-doctor → hook-doctor skill
- **Generates structured A/B prompts** when both files exist — shows project distribution, "Seen in:" counts, and waits for user choice

Routing rules the agent must follow:
- **Only one file exists** → route there silently, no prompt needed
- **Both global and project files exist** → show the A/B prompt from `router.format_ab_prompt()` and wait for user choice
- **Neither exists** → ask which to create before proceeding
- **⚠️ Writing to `~/.claude/CLAUDE.md` affects every future session across all projects** — require explicit consent
- **Checklist entries must carry target annotations** — `(global → ~/.claude/CLAUDE.md)` or `(project: repo-name → .claude/CLAUDE.md)`

## 3. Report

Present recommendations ordered by impact. For each: rule text, evidence, routed target file (with annotation), estimated tokens saved, and confidence (high/medium/low). User approves or skips each rule individually.

If the scorer reports a file over 200 lines, run `references/recipe-book.md` **before** presenting the report — the bloat must be remediated first or new rules will compound the problem. If the score is 0.0 (5000+ lines), the recipe book is mandatory.

Use `router.format_checklist()` to display annotated checklist entries with target-file annotations.

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

## Reference Files

Load these as needed during the audit — they are not loaded automatically:

| File | When to read |
|------|-------------|
| `references/category-guide.md` | Phase 2 — interpreting pattern categories and thresholds |
| `references/governance.md` | Phase 4 — SOSA™ approval rules before any file write |
| `references/noise-filters.md` | When false positives appear — the 7 filter categories and how to add new ones |
| `references/recipe-book.md` | When CLAUDE.md exceeds 200 lines — 4-step bloat remediation + stacked PR cascade rebase procedure |
| `references/karpathy-guardrails.md` | Phase 5 — opt-in guardrails merge procedure |

Re-run the audit every 2–4 weeks, or after significant workflow changes. Delta comparisons against the persisted baseline keep repeated runs meaningful.
