# Quicknotes

Fast, zero-subprocess quick-note capture and management for Claude Code.

## Why This Exists

The [original quicknotes plugin](https://github.com/litianningdatadog/claude-marketplace/tree/main/quicknotes) launches Python for every operation — `python3 scripts/qn.py capture "text"` — paying Python VM startup + import overhead (~300-500ms) per invocation. This version eliminates all Python subprocesses: the Claude Code agent uses its already-running built-in tools (Write, Read, Bash, Grep, Edit) to directly manipulate note files. Same functionality, same storage format, **10x faster**.

## Quick Start

### Capture a note
```
/qn Buy milk and eggs for the week #groceries
```
→ `✓ noted [a1b2] "Buy milk and eggs for the week"  tags: groceries`

### List your notes
```
/qn list
```

### Search notes
```
/qn search milk
```

### Show a note
```
/qn show a1b2
```

### Complete a note
```
/qn done a1b2
```

### Past-due notes
```
/qn due
```

### Notes for this project
```
/qn here
```

## Operations

| Command | Description |
|---------|-------------|
| `qn <text> [#tags]` | Capture a note (default) |
| `qn list [--project P] [--tag T]` | List all notes |
| `qn search <query>` | Fuzzy search across title/body/tags |
| `qn show <id\|fuzzy>` | Full metadata, body, and refs |
| `qn done <id\|fuzzy>` | Complete — deletes the note |
| `qn update <id\|fuzzy> [flags]` | Edit title, tags, priority, due, body |
| `qn due` | Past-due notes |
| `qn here` | Notes for current project/dir |
| `qn ref <a> <b>` | Link two notes bidirectionally |

## Natural Language Triggers

The skill auto-activates when you say things like:
- "jot this down: ..."
- "note to self: ..."
- "remind me to ..."
- "write a quick note ..."
- "what notes do I have?"
- "list my notes"
- "mark note done"

## Session Reminders (Opt-in)

Enable proactive reminders at session start. The skill will ask before installing — approve it, and you'll see:

```
📝 quicknotes: 3 due, 2 open for this project  (run `qn due` / `qn here`)
   • due: Buy milk
   • due: Review quarterly budget
```

Always silent when there's nothing due.

## Shell Alias (Opt-in)

For CLI use outside Claude Code:
```bash
bash scripts/install_alias.sh
```
Adds a `qn()` function to your shell RC. Then `qn buy milk #groceries` works from any terminal.

## Storage

Notes live at `~/.quicknotes/notes/<id>.md` as Markdown files with JSON frontmatter. You can read, edit, or version-control them directly.

```
~/.quicknotes/
└── notes/
    ├── 20260628-143022-a1b2.md
    ├── 20260627-090000-cc33.md
    └── ...
```

Format is 100% compatible with the original Python-based quicknotes plugin.

## Architecture

No Python scripts for core operations. The Claude Code agent uses its built-in tools directly:
- **Write** — create note files
- **Read** — read note contents
- **Bash** — fast metadata queries (dates, git info, listing)
- **Grep** — search notes
- **Edit** — update note fields

See `references/tech-doc.md` for full technical details.

## Comparison

| | Original (Python) | This Version |
|---|---|---|
| Capture time | ~350-500ms | ~50ms |
| Python dependency | Required | None |
| Subprocess per op | Yes (python3) | No (bash for metadata only) |
| Storage format | `~/.quicknotes/notes/*.md` | Same — 100% compatible |

## License

MIT
