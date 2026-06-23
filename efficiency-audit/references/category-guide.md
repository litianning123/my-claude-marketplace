# Category Interpretation Guide

Thresholds for converting findings into recommendations:

| Category | Threshold | Default Rule Pattern |
|----------|-----------|---------------------|
| corrections | count >= 3 | Behavioral rule targeting preceding_action |
| missing_context | sessions >= 3 | Stable fact for CLAUDE.md |
| slow_start_context | sessions >= 2 | Orientation content for CLAUDE.md |
| automation_candidates | count >= 2 | Hook or alias proposal |
| git_workflow_errors | count >= 2 | Procedure block (local vs origin refs) |

## corrections

Messages where the user redirected Claude. Use `preceding_action` (what Claude did right before the correction) to draft a targeted rule.

## missing_context

Messages where the user re-explained stable facts. Route to project CLAUDE.md via `top_project`.

## slow_start_context

Messages that orient Claude at session start. Ask: stable (always true) or transient (task-specific)? Stable goes in CLAUDE.md.

## git_workflow_errors

Stale remote refs in cascade rebases. The key invariant: in a single pipeline command, reference LOCAL branch names, not `origin/<branch>` — the remote tracking ref is stale until after push.

## hook_errors

Failing hooks detected in transcripts. Route to hook-doctor for diagnosis. Do not infer hook health from session-level success messages.
