# my-claude-marketplace

A collection of [Claude Code](https://claude.com/claude-code) **plugins** — each delivering a skill that extends Claude's capabilities with a specialized, repeatable workflow.

Each plugin has a `.claude-plugin/plugin.json` manifest and a `skills/<name>/SKILL.md` that becomes Claude's operating instructions once the skill activates. Supporting scripts live under `<plugin>/scripts/`. No build system or third-party dependencies — skills are Markdown plus stdlib-only Python.

## Plugins

| Skill | What it does |
|-------|--------------|
| [`hook-doctor`](hook-doctor/) | Inspects and repairs Claude Code hook configurations. Detects 7 common misconfigurations (unquoted path variables, missing/non-executable scripts, unknown events, invalid JSON, missing command fields, deprecated syntax) and applies safe, idempotent fixes for the 2 auto-fixable ones. |
| [`efficiency-audit`](efficiency-audit/) | Analyzes Claude Code conversation transcripts to surface recurring inefficiencies — corrections, missing context, slow starts, automation candidates, git workflow errors, tool failures, and hook errors — then generates fix recommendations via heuristic rule engine and applies them as idempotent marker blocks in CLAUDE.md. |
| [`quicknotes`](quicknotes/) | Fast, zero-subprocess quick-note capture and management. The agent uses built-in tools (Write, Read, Bash, Grep, Edit) directly — no Python overhead. Supports capture, list, search, show, done, update, due, here, and ref (bidirectional linking). Notes are centralized markdown files with JSON frontmatter. |

## Development

No build system or third-party dependencies. Scripts that ship tests use Python standard-library `unittest`, run from the script's directory:

```bash
# hook-doctor
cd hook-doctor/scripts && python3 -m unittest test_doctor -v

# efficiency-audit
cd efficiency-audit/scripts && python3 -m unittest test_audit -v
```

## Adding a new plugin

1. Create a top-level directory named in kebab-case (matches the plugin's name).
2. Add a `.claude-plugin/plugin.json` with `name` and `description`.
3. Add `skills/<name>/SKILL.md` as the agent procedure. Front-load trigger phrases in the frontmatter `description` — it's the only text read when deciding whether to activate. Reference supporting scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/...` (resolved dynamically at runtime).
4. Put supporting code under `<plugin>/scripts/`.
5. Register the plugin in `.claude-plugin/marketplace.json` — add an entry to the `plugins` array with `name`, `source`, `description`, `version`, `homepage`, and `repository`.
6. Add the plugin to the table above.

## License

MIT
