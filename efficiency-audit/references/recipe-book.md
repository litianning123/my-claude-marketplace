# Recipe Book — CLAUDE.md Bloat Remediation

When a `CLAUDE.md` file exceeds ~200 lines, domain-specific rules should be extracted into path-scoped files under `.claude/rules/`. This keeps the root file scannable while ensuring specialized rules still load in the right contexts.

This is distinct from the scorer's thresholds (300→750→5000 lines) — the scorer measures continuous bloat; this is a structural refactor.

## When to Run

After Phase 1, check line counts:

```bash
wc -l ~/.claude/CLAUDE.md
wc -l .claude/CLAUDE.md
wc -l CLAUDE.md
```

If **any** file exceeds 200 lines, run this procedure **before** adding new audit rules. A 0.0 score from `score_efficiency.py` (5000+ lines) makes this mandatory.

---

## The 4-Step Procedure

### Step 1 — Classify Every Rule

Read the entire CLAUDE.md and classify each rule or section as one of:

| Classification | Criteria | Destination |
|---------------|----------|-------------|
| **Core** | Applies everywhere — project architecture, universal instructions, SOSA governance, commit conventions | Stays in root CLAUDE.md |
| **Domain-scoped** | Applies only to specific file types, directories, tools, or languages | Extracted to `.claude/rules/<name>.md` |

Display findings as a table:

```
| Rule (first 60 chars) | Classification | Suggested scope |
|-----------------------|----------------|-----------------|
| NEVER commit without explicit instruction... | Core | — |
| Use type hints in all Python files... | Domain | python.md — all **/*.py |
| Run gofmt before committing... | Domain | go.md — all **/*.go |
| SQL queries must use parameterized... | Domain | sql.md — all **/*.sql |
```

**Stop and ask for user approval before proceeding.** The user may reclassify rules.

### Step 2 — Draft Path-Scoped Rule Files

For each domain group identified in Step 1, draft a file under `.claude/rules/<name>.md` with YAML frontmatter:

```yaml
---
description: Python conventions and tooling rules
paths:
  - "**/*.py"
  - "**/pyproject.toml"
  - "**/requirements*.txt"
---

# Python Conventions

- Always use type hints for function signatures
- Prefer `pathlib.Path` over `os.path`
- Run `pytest` before committing — never push failing tests
```

Frontmatter reference:

| Key | Required | Example | Notes |
|-----|----------|---------|-------|
| `description` | recommended | `"Python conventions"` | Human-readable label |
| `paths` | required for scoping | `["**/*.py", "**/pyproject.toml"]` | Glob patterns — file must match at least one to trigger loading |

Omitting `paths` means the file loads in all contexts — only appropriate for truly universal additions that don't belong in root.

**Show full proposed content for every file before writing.**

### Step 3 — Draft the Trimmed Root CLAUDE.md

Produce a new root file containing **only Core rules and project architecture**. Domain-scoped rules are replaced with a reference to the extracted file:

```markdown
Domain-specific rules live in `.claude/rules/`:
- Python: `.claude/rules/python.md`
- Go: `.claude/rules/go.md`
- SQL: `.claude/rules/sql.md`
```

**Show the full new content as a diff or complete block before writing.** The trimmed file should be well under 200 lines.

### Step 4 — Apply

Apply in this order (SOSA™ governance — one approval per step):

1. **Create `.claude/rules/*.md` files first** — additive, each independently revertible.
2. **Trim `CLAUDE.md` second** — only after rules files are confirmed correct.

Verify:
- Frontmatter is valid YAML in every rules file
- `wc -l CLAUDE.md` is now under 200
- No rules were lost — the total rule set across root + rules files covers everything from the original

---

## Stacked PR Cascade Rebase Procedure

Triggered when `git_workflow_errors` count ≥ 2, or a stale-remote-ref correction is observed during stacked-PR rebase cascades.

### The Problem

In a compound command that updates multiple stacked branches and pushes at the end:

```bash
# ❌ WRONG — origin/<branch> is stale until after git push
git checkout base-branch && git pull && \
  git checkout pr-1 && git rebase base-branch && git push -f && \
  git checkout pr-2 && git reset --hard origin/pr-1 && git rebase pr-1 && git push -f
```

`origin/pr-1` is a remote tracking ref. It remains stale until `git push` completes and the remote acknowledges. If a later step resets to that stale ref, it silently picks up the OLD commit — placing the next branch on the wrong base.

### The Rule

> During cascading rebases across stacked PRs in a single command, **always reference the LOCAL branch name**, never `origin/<branch>`.

```bash
# ✓ CORRECT — reference local branches
git checkout base-branch && git pull && \
  git checkout pr-1 && git rebase base-branch && git push -f && \
  git checkout pr-2 && git reset --hard pr-1 && git rebase pr-1 && git push -f
```

`pr-1` (local) is updated by the rebase in the previous step. `origin/pr-1` only updates on fetch or push — it lags behind until the push completes.

### Routing

- If the error is project-specific (observed in a single repo) → route to project `CLAUDE.md`
- If the user does stacked PRs across multiple repos → route to global `~/.claude/CLAUDE.md`
