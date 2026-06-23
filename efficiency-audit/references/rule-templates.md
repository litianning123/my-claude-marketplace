# Rule Templates

Templates for the heuristic synthesis engine. Edit this file to improve rule quality without changing Python code.

## Template Format

Each entry: `## CATEGORY_NAME` followed by YAML-style fields:

- `min_count`: minimum occurrences to trigger a recommendation
- `min_sessions`: minimum distinct sessions
- `tokens_per`: estimated token savings per occurrence
- `target`: file to write to (CLAUDE.md, settings.json, memory, hook-doctor)
- `template`: rule text with {placeholders}

Placeholders: {count}, {sessions}, {top_project}, {example}, {preceding_action}

---

## corrections

min_count: 3
min_sessions: 2
tokens_per: 100
target: CLAUDE.md
template: |
  NEVER {action_heuristic}. Found {count} correction(s) across {sessions} session(s) in {top_project}.
  Example: "{example}"
  Claude's preceding action: "{preceding_action}"

---

## missing_context

min_count: 2
min_sessions: 3
tokens_per: 200
target: CLAUDE.md
template: |
  ADD to CLAUDE.md: stable project fact that was re-explained {count} times across {sessions} sessions.
  Example: "{example}"

---

## slow_start_context

min_count: 2
min_sessions: 2
tokens_per: 150
target: CLAUDE.md
template: |
  ADD orientation to CLAUDE.md: per-session context that was explained {count} times across {sessions} sessions.
  Example: "{example}"

---

## automation_candidates

min_count: 2
min_sessions: 2
tokens_per: 150
target: settings.json
template: |
  CONSIDER automation: recurring pattern detected {count} times across {sessions} sessions in {top_project}.
  Example: "{example}"

---

## git_workflow_errors

min_count: 2
min_sessions: 1
tokens_per: 200
target: CLAUDE.md
template: |
  ADD git workflow procedure to CLAUDE.md: stale-ref or cascade-rebase issue detected {count} times across {sessions} sessions in {top_project}.
  Key invariant: in a single cascade command, always reference the LOCAL branch name, not origin/<branch> (remote tracking ref is stale until after push).
  Example: "{example}"

---

## hook_errors

min_count: 1
min_sessions: 1
tokens_per: 0
target: hook-doctor
template: |
  Run hook-doctor to scan all hook configs for static issues. {count} hook error(s) found across {sessions} session(s).
  Hook errors are configuration failures — not candidates for CLAUDE.md rules.
