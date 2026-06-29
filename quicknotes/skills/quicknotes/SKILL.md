---
name: quicknotes
description: "'qn', 'quicknotes', 'write a quick note', 'jot this down', 'note to self', 'remind me to', 'add a note', 'list my notes', 'mark note done', 'what notes do I have', 'notes for this project' — Capture and manage quick notes with near-zero friction. Notes are centralized markdown files with JSON frontmatter (date, project, dir, tags, priority, due, refs), fuzzy-searchable, with references and time/location reminders; completing a note removes it."
---

# Quicknotes (Tool-Based)

All operations use Claude's built-in tools (Write, Read, Bash, Grep, Edit) to directly manipulate note files under `~/.quicknotes/notes/`. **No external scripts are spawned for core operations.** The agent's tools are already loaded — using them eliminates all Python VM and import overhead.

## Storage Format

Notes live at `~/.quicknotes/notes/<id>.md`. Each file uses JSON-value YAML frontmatter (parseable by both `json` and YAML parsers):

```
---
id: "20260628-143022-a1b2"
title: "First line of body (max 80 chars)"
created: "2026-06-28T14:30:22Z"
updated: "2026-06-28T14:30:22Z"
priority: null
project: "my-project"
cwd: "/Users/foo/my-project"
branch: "main"
tags: ["tag1", "tag2"]
due: null
refs: []
---
Body text here. May contain #inline-hashtags which are parsed during capture.
```

All times are ISO-8601 UTC. Tags are lowercase, no `#` prefix, internal spaces replaced with `-`. The `refs` array stores bidirectional note IDs.

## Global Rules

1. **NEVER fabricate IDs** — use the bash-generated timestamp+hex format described below.
2. **NEVER read or write outside `~/.quicknotes/`.** Before any file operation, verify the resolved path lives under the notes directory. Path traversal is prevented by the ID format (`[0-9A-Za-z._-]+` — no `/` or `..` possible), but verify anyway.
3. **`done` is destructive** — always warn with the note title and ask for confirmation before deleting.
4. **Fuzzy ambiguity** — if a reference resolves to 2+ candidates, show the list (ID, title, project) and ask the user to pick. Never auto-pick.
5. **Keep replies terse** — one line for capture/list/search/done/update. Full detail only for `show`.
6. **Tags are JSON arrays**: `["tag1", "tag2"]`. Use proper JSON syntax (double quotes, comma-separated).
7. **Always use `mkdir -p`** before writing any note — the notes directory may not exist yet.

---

## Operation 1: Capture (default — any text that isn't a management verb)

Capture creates a new note. Use this path when the skill is auto-triggered by phrases like "jot this down" or "note to self." For `/qn` slash command captures, see `commands/qn.md`.

### Step 1: Gather metadata (one Bash call)

```bash
ID=$(echo "$(date -u +'%Y%m%d-%H%M%S')-$(od -vAn -N2 -tx1 /dev/urandom | tr -d ' \n')")
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CWD=$(pwd)
PROJECT=$(git -C "$CWD" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||')
[ -z "$PROJECT" ] && PROJECT=$(basename "$CWD")
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "null")
echo "ID=$ID NOW=$NOW CWD=$CWD PROJECT=$PROJECT BRANCH=$BRANCH"
```

### Step 2: Parse the note text

1. **Extract `#hashtags`**: Find all `#word` patterns that are at word boundaries (not mid-word like `issue#42` or `C#`). Remove them from the body. Normalize: lowercase, strip `#`, collapse internal whitespace to `-`. Deduplicate preserving order.
2. **Derive title**: First line of the remaining body text, max 80 characters. If body is empty, title = "(untitled)".
3. **Parse time expressions**: If the text contains phrases like "by Friday", "tomorrow 5pm", "due next Monday", compute the ISO-8601 UTC instant and set `due`. If unsure about the exact time, set it to end-of-day (23:59:59Z) of the mentioned date.
4. **Suggest 1-3 tags** from context if the user didn't provide any, but **don't block capture** on tagging — accept the note immediately.

### Step 3: Build and write the file

Use the **Write** tool to create `~/.quicknotes/notes/<ID>.md`:

```
---
id: "<ID>"
title: "<title>"
created: "<NOW>"
updated: "<NOW>"
priority: null
project: "<PROJECT>"
cwd: "<CWD>"
branch: <BRANCH or null>
tags: [<comma-separated double-quoted tags>]
due: <ISO-8601 or null>
refs: []
---
<body text with hashtags removed>
```

If BRANCH was detected as a git branch, store it unquoted (not `"null"` — use the JSON literal `null`).

### Step 4: Confirm

```
✓ noted [<last-4-hex-chars-of-ID>] "<title>"  tags: <tag1, tag2, ...>
```

Keep the confirmation to one line. Include the due date if one was parsed.

---

## Operation 2: List

### Step 1: Gather metadata from all notes (one Bash call)

```bash
NOTES_DIR="${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes"
for f in $(ls -t "$NOTES_DIR"/*.md 2>/dev/null); do
  [ -f "$f" ] || continue
  id=$(head -3 "$f" | grep '^id:' | head -1 | sed 's/^id:[[:space:]]*"//; s/".*//')
  [ -z "$id" ] && continue
  title=$(head -6 "$f" | grep '^title:' | head -1 | sed 's/^title:[[:space:]]*"//; s/".*//')
  project=$(head -10 "$f" | grep '^project:' | head -1 | sed 's/^project:[[:space:]]*"//; s/".*//')
  tags=$(head -13 "$f" | grep '^tags:' | head -1 | sed 's/^tags:[[:space:]]*//; s/^\[//; s/\]$//; s/",[[:space:]]*"/ /g; s/"//g')
  due=$(head -13 "$f" | grep '^due:' | head -1 | sed 's/^due:[[:space:]]*//; s/"//g; s/,$//; s/^[[:space:]]*null[[:space:]]*$//')
  prio=$(head -10 "$f" | grep '^priority:' | head -1 | sed 's/^priority:[[:space:]]*//; s/"//g; s/,$//; s/^[[:space:]]*null[[:space:]]*$//')
  echo "$id|$title|$project|$tags|$due|$prio"
done
```

### Step 2: Filter and display

- **No args**: Show all notes, newest first. If empty: "No notes."
- **`--project P`**: Filter to notes whose project field matches P (case-insensitive).
- **`--tag T`**: Filter to notes whose tags array contains T (normalize T first: lowercase, hyphenate spaces).
- **`--priority P`**: Filter by priority level.

### Step 3: Format each line

```
<last-4-hex-of-ID>  <title>  (project)  #tag1 #tag2  !priority  due:YYYY-MM-DD
```

If a note has no project, omit `(project)`. If no tags, omit `#tags`. If no priority, omit `!priority`. If no due date, omit `due:`.

---

## Operation 3: Search

### Step 1: Find matching files (Grep)

```bash
grep -il "<query>" "${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes/"*.md 2>/dev/null
```

If no matches: "No matches for '<query>'."

### Step 2: Score and rank

For each matching file, **Read** the frontmatter and body. Compute a simple relevance score:
- Whole query match in title: +3
- Whole query match in body: +2
- Whole query match in tags/project: +1
- Individual word matches: +1 each

### Step 3: Display

Show matches ranked by score, using the same format as List (ID, title, project, tags, priority, due). Limit to 20 results.

---

## Operation 4: Show

### Step 1: Resolve the target

First, try exact ID match: check if `~/.quicknotes/notes/<ref>.md` exists. If yes, that's the note.

If not, perform a fuzzy search:
```bash
grep -il "<lowercased-ref>" "${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes/"*.md 2>/dev/null
```

- **0 matches**: "No note matching '<ref>'."
- **1 match**: Use that file.
- **2+ matches**: List candidates (ID, title, project). Ask user to pick by ID or number. Wait for response.

### Step 2: Read and display

Use **Read** on the resolved file. Display:

```
Id:       20260628-143022-a1b2
Title:    Buy milk
Priority: high
Due:      2026-06-29 17:00 PDT
Created:  2026-06-28 07:30 PDT
Updated:  2026-06-28 14:30 PDT
Project:  my-project  (branch: main)
Cwd:      /Users/foo/my-project
Tags:     #groceries #urgent
Refs:     [20260627-090000-cc33] Review quarterly budget
─────────────────────────────────────────────────
Buy milk and eggs for the week. #groceries
```

Convert timestamps to local time for display using `date -j -f "%Y-%m-%dT%H:%M:%SZ" "<iso>" "+%Y-%m-%d %H:%M %Z"` (macOS) or `date -d "<iso>" "+%Y-%m-%d %H:%M %Z"` (Linux).

Expand refs: for each ref'd ID, read that note's title and show it.

---

## Operation 5: Done (Complete/Delete)

### Step 1: Resolve the target

Same resolution as Show (exact ID → fuzzy search → candidate list).

### Step 2: Confirm

Show the note title and ask for confirmation:
```
Delete "[title]" ([id])? This is permanent (recoverable from git history if notes dir is a repo).
```

Wait for explicit "yes" or "y" before proceeding. Do NOT delete on "maybe" or "show me first."

### Step 3: Delete

```bash
rm "${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes/<id>.md"
```

### Step 4: Confirm

```
✓ done (removed): [<last-4-hex>] "<title>"
```

---

## Operation 6: Update

### Step 1: Resolve the target

Same resolution as Show.

### Step 2: Parse update flags

- `--title "New Title"` → replace title
- `--tag t1 --tag t2` → replace entire tag list (normalize each tag)
- `--priority high|medium|low` → replace priority
- `--due 2026-07-04T17:00:00Z` → replace due date
- Any remaining text after flags → replace body
- Inline `#hashtags` in new body → extract and merge with `--tag` tags

### Step 3: Apply changes

Use **Read** to get the current file. Then use **Edit** to update specific frontmatter fields, or **Write** to replace the entire file. Always update `"updated"` to current UTC time.

### Step 4: Confirm

```
✓ updated [<last-4-hex>] "<title>"
```

---

## Operation 7: Due

### Step 1: Find past-due notes (Bash)

```bash
NOTES_DIR="${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
for f in "$NOTES_DIR"/*.md; do
  [ -f "$f" ] || continue
  DUE=$(head -13 "$f" | grep '^due:' | head -1 | sed 's/^due:[[:space:]]*//; s/"//g; s/,$//')
  [ -z "$DUE" ] && continue
  [ "$DUE" = "null" ] && continue
  # ISO-8601 lexicographic comparison IS chronologically correct
  [ "$DUE" \< "$NOW" ] || continue
  echo "$f"
done
```

### Step 2: Display

If empty: "Nothing due."

Otherwise, use **Read** on each file to get title/tags/priority. Format as a list with due dates converted to local time. Sort by due date (oldest first). Show overdue duration: "3 days overdue", "1 hour overdue."

---

## Operation 8: Here

### Step 1: Detect current context (Bash)

```bash
CWD=$(pwd)
PROJECT=$(git -C "$CWD" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||')
[ -z "$PROJECT" ] && PROJECT=$(basename "$CWD")
echo "PROJECT=$PROJECT CWD=$CWD"
```

### Step 2: Find matching notes (Bash)

```bash
NOTES_DIR="${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes"
for f in "$NOTES_DIR"/*.md; do
  [ -f "$f" ] || continue
  proj=$(head -10 "$f" | grep '^project:' | head -1 | sed 's/^project:[[:space:]]*"//; s/".*//')
  cwd=$(head -10 "$f" | grep '^cwd:' | head -1 | sed 's/^cwd:[[:space:]]*"//; s/".*//')
  [ "$proj" = "$PROJECT" ] && echo "$f" && continue
  [ "$cwd" = "$CWD" ] && echo "$f" && continue
done
```

### Step 3: Display

If empty: "No open notes for this project/dir."

Otherwise, format as list showing ID, title, tags, priority, due. Newest first.

---

## Operation 9: Ref (Link Notes)

### Step 1: Resolve both targets

Resolve note A and note B independently using the same resolution as Show (exact ID first, then fuzzy search). If either fails, stop and report which one.

### Step 2: Prevent self-links

If both resolve to the same note: "Cannot link a note to itself."

### Step 3: Add bidirectional refs

**Read** both files. Use **Edit** to add each note's ID to the other's `"refs"` array. If A already has B's ID in refs, skip that direction (don't duplicate). Update `"updated"` timestamp on both.

### Step 4: Confirm

```
✓ linked [<last-4-hex-A>] "<title-A>" ↔ [<last-4-hex-B>] "<title-B>"
```

---

## Session Reminder (Opt-in)

To enable proactive reminders at session start, offer to install this hook:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/session_reminder.sh\""
      }
    ]
  }
}
```

The hook script prints a one-line summary of due notes and notes open for the current project. It always exits 0 (never blocks session start). The script is at `scripts/session_reminder.sh`.

**Ask for consent before installing.** Describe what it does: "This will show a quick reminder at the start of each session if you have due notes or notes for the current project. Always silent when there's nothing to report." Never auto-install.
