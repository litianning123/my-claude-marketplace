# Quicknotes — Technical Documentation

## Architecture

Quicknotes has two execution paths, both using Claude Code's built-in tools with **zero Python subprocess overhead**:

### Path 1: Slash Command (`/qn`)
The `commands/qn.md` file pre-computes context (ID, timestamp, project, branch, CWD) at load time using `!` inline command syntax. For captures, the agent uses the **Write** tool directly — no subprocess at all. Management verbs delegate to the skill.

### Path 2: Skill Auto-Trigger
When the user says "jot this down", "note to self", etc., the `skills/quicknotes/SKILL.md` activates. The agent follows the tool-based playbook: one **Bash** call for metadata collection, then **Write** for file creation.

### Comparison with the Original

| Aspect | Original (Python) | New (Tool-Based) |
|--------|-------------------|------------------|
| Capture | `python3 qn.py capture "text"` | Write tool directly (command) or Bash + Write (skill) |
| List | Python glob + read_note loop | Bash one-liner with sed field extraction |
| Search | Python haystack scoring | Grep + Read matching files |
| Show | Python read_note + format | Read tool directly on file |
| Done | Python resolve + os.unlink() | Bash `rm` after Grep resolve |
| Update | Python read + dict merge + rewrite | Read + Edit/Write |
| SessionStart | Python VM + import notes_store | Bash script (~5ms startup) |
| Python startup per op | ~100-200ms | 0ms (no Python) |
| Dependencies | Python 3 + notes_store module | bash, grep, sed (all POSIX) |

## Storage Format

```
~/.quicknotes/notes/<id>.md
```

Each file is a Markdown file with JSON-value YAML frontmatter:

```yaml
---
id: "20260628-143022-a1b2"
title: "First line of body (max 80 chars)"
created: "2026-06-28T14:30:22Z"
updated: "2026-06-28T14:30:22Z"
priority: null          # null | "high" | "medium" | "low"
project: "my-project"   # git repo name or directory basename
cwd: "/Users/foo/proj"  # absolute path where note was created
branch: "main"          # git branch, or null
tags: ["tag1", "tag2"]  # JSON array, lowercase, no #, spaces→hyphens
due: null               # ISO-8601 UTC, or null
refs: []                # bidirectional note ID links
---
Body text goes here. Hashtags are extracted during capture.
```

All timestamps are ISO-8601 UTC. Tags are normalized: lowercase, no `#`, internal whitespace collapsed to `-`.

## Field Reference

| Field | Type | Editable | Description |
|-------|------|----------|-------------|
| `id` | string | No | `YYYYMMDD-HHMMSS-XXXX` (auto-generated) |
| `title` | string | Yes | First line of body, max 80 chars |
| `created` | ISO-8601 | No | Creation timestamp in UTC |
| `updated` | ISO-8601 | Auto | Last modification timestamp in UTC |
| `priority` | null/string | Yes | `null`, `"high"`, `"medium"`, `"low"` |
| `project` | string | No | Git repo name or directory basename |
| `cwd` | string | No | Absolute working directory at capture time |
| `branch` | string/null | No | Git branch at capture time, or `null` |
| `tags` | [string] | Yes | JSON array of normalized tags |
| `due` | string/null | Yes | ISO-8601 UTC deadline, or `null` |
| `refs` | [string] | Auto | Bidirectional note ID links |

## ID Format

```
YYYYMMDD-HHMMSS-XXXX
```

- `YYYYMMDD` — UTC date
- `HHMMSS` — UTC time (seconds)
- `XXXX` — 4 random hex characters from `/dev/urandom`

Example: `20260628-143022-a1b2`

Generated via: `date -u +'%Y%m%d-%H%M%S'` + `od -vAn -N2 -tx1 /dev/urandom`

## Operations Reference

### Capture
Creates a new note. Extracts `#hashtags`, derives title from first line, parses time expressions for due dates.

### List
Lists all notes newest-first. Filterable by `--project`, `--tag`, `--priority`.

### Search
Grep-based search scored by match count and match location (title > body > tags).

### Show
Displays full metadata + body + expanded refs. Converts UTC timestamps to local time.

### Done
Permanently deletes the note file. Always asks for confirmation. Recoverable from git if notes dir is a repo.

### Update
Edits title, tags, priority, due, or body. Updates the `updated` timestamp.

### Due
Shows past-due notes sorted oldest-first with overdue duration.

### Here
Shows notes matching current project or current working directory.

### Ref
Creates bidirectional links between two notes.

## Session Reminder Hook

`scripts/session_reminder.sh` is a bash script for use as a SessionStart hook. It prints:

```
📝 quicknotes: 3 due, 2 open for this project  (run `qn due` / `qn here`)
   • due: Buy milk
   • due: Review quarterly budget
   • due: Schedule dentist appointment
```

Always exits 0. Silent when there's nothing to report.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUICKNOTES_HOME` | `~/.quicknotes` | Root directory for notes storage |

## Path Traversal Protection

Note IDs are restricted to `[0-9A-Za-z._-]+` by the timestamp+hex format — no path separators or traversal characters (`/`, `..`) are possible. Operations that read/write notes verify the resolved path is within the notes directory before proceeding.
