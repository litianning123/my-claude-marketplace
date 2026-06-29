---
name: qn
description: "Capture or manage a quick note with zero Python overhead. Default (any text): fast capture with auto-detected project/branch/hashtags. Management verbs: list, search, show, done, update, due, here, ref. Uses pre-computed context for zero-subprocess captures."
argument-hint: "<note text [#tags]> | list | search <query> | show <id> | done <id> | update <id> | due | here | ref <a> <b>"
---

Input: `$ARGUMENTS`

## Pre-computed Context

These resolve at load time — zero runtime cost:

- **ID**: !`echo "$(date -u +'%Y%m%d-%H%M%S')-$(od -vAn -N2 -tx1 /dev/urandom | tr -d ' \n')"`
- **Now**: !`date -u +"%Y-%m-%dT%H:%M:%SZ"`
- **CWD**: !`pwd`
- **Project**: !`git -C "$(pwd)" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||' || basename "$(pwd)"`
- **Branch**: !`git -C "$(pwd)" rev-parse --abbrev-ref HEAD 2>/dev/null || echo null`

## If Empty or Help

If `$ARGUMENTS` is empty, starts with `-h`, `--help`, or `help` — show usage:

```
Usage: qn <note text> [#tag …]          capture a note (DEFAULT)
       qn list [--project P] [--tag T]  list notes
       qn search <query>                fuzzy search across title/body/tags/project
       qn show   <id|fuzzy>             full metadata + body + refs
       qn done   <id|fuzzy>             complete — DELETES the note file
       qn update <id|fuzzy> [...flags]  edit title, tags, priority, due, body
       qn due                           past-due notes
       qn here                          notes for this project/dir
       qn ref    <id|fuzzy> <id|fuzzy>  link two notes bidirectionally
```

## Management Verbs

If `$ARGUMENTS` starts with one of: `list`, `search`, `show`, `done`, `update`, `due`, `here`, `ref`, `add` —

**Activate the quicknotes skill** (Skill tool) and follow its tool-based procedures in SKILL.md. The skill has complete, battle-tested instructions for each operation using built-in tools (Write, Read, Bash, Grep, Edit).

For the `add` verb: treat it as an explicit capture command. The rest of the arguments become the note text. This handles edge cases like `qn add list the migration steps` where the note text starts with a reserved word.

## Fast Capture (default — any other input)

The input IS the note text. Use the pre-computed context above.

### 1. Parse the input

a) **Extract inline `#hashtags`**: Find words matching `#` at word boundaries — not mid-word like `issue#42` or `C#`. Remove them from the body. Normalize tags: lowercase, strip `#`, replace internal spaces with `-`. Deduplicate preserving order.

b) **Derive title**: First line of the remaining body, max 80 characters. If body is empty after stripping hashtags, title = "(untitled)".

c) **Parse time expressions**: If the text contains phrases like "by Friday", "tomorrow 5pm", "due next Monday" — compute the ISO-8601 UTC instant and set `due`. If unsure about exact time, default to end-of-day (23:59:59Z) of the mentioned date.

d) **Suggest tags**: If no tags were provided, suggest 1-3 from context (current project name, task type keywords in the text, etc.). Don't block — accept the note immediately.

### 2. Build the frontmatter

Construct JSON-value YAML frontmatter using the pre-computed context:

```
---
id: "<ID>"
title: "<title>"
created: "<Now>"
updated: "<Now>"
priority: null
project: "<Project>"
cwd: "<CWD>"
branch: <Branch or null>
tags: ["tag1", "tag2"]
due: <ISO-8601 or null>
refs: []
---
```

**Important**: The Branch field — if pre-computed Branch is a git branch name, write it quoted: `"main"`. If pre-computed Branch is the literal string `null`, write the JSON literal `null` (no quotes).

### 3. Write the note

Use the **Write** tool to create `~/.quicknotes/notes/<ID>.md` with the frontmatter and body (hashtags stripped).

The notes directory is auto-created if needed (Write handles this — but if it fails with "no such directory", run `mkdir -p ~/.quicknotes/notes` first).

### 4. Confirm (one line)

```
✓ noted [<last-4-hex-of-ID>] "<title>"  tags: <comma-separated>
```

If a due date was parsed, append `due: <human-readable date>` to the confirmation.

### 5. If the user follows up with changes

If the user immediately adds "and tag it #urgent" or "with priority high" after the capture confirmation, apply those updates using the Update operation (Edit the frontmatter fields, update the `"updated"` timestamp). Don't create a second note.

## Capture via Skill Trigger

When the user triggers capture without the slash command (e.g., "jot this down: buy milk"), the **quicknotes skill** auto-activates. The skill's SKILL.md has equivalent capture instructions using Bash for metadata collection + Write for file creation. The pre-computed context in this command file is faster (no Bash subprocess), so prefer the slash command for explicit captures.
