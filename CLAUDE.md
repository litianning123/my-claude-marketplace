# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this repository is

A collection of **Claude Code plugins**. Each plugin is a self-contained directory that extends Claude's capabilities with specialized workflows. There is no build system or dependency manifest — plugins are authored as Markdown + stdlib-only Python scripts.

## Plugin anatomy

A plugin lives in its own top-level directory:

- `.claude-plugin/plugin.json` — required. Plugin manifest with `name` and `description`.
- `skills/<name>/SKILL.md` — required. YAML frontmatter with `name` and `description` (load-bearing — this is the only text the agent reads to decide whether to activate). The Markdown body is loaded only after activation.
- `scripts/` — optional supporting Python code (stdlib only).
- `README.md` — human-facing documentation (English).
- `README.zh-CN.md` — Chinese translation of the human-facing documentation.

## Conventions

### README bilingual requirement

Every plugin (and the marketplace root) must have both `README.md` (English) and `README.zh-CN.md` (Chinese). Each file must include a cross-link to the other language directly under the title:

- English README: `[中文](README.zh-CN.md)`
- Chinese README: `[English](README.md)`

When adding or updating a README, keep both language versions in sync — same sections, same order, same structure.

### Skill & script conventions

- Write the SKILL.md body as a procedure for the agent to follow, not as end-user documentation.
- Front-load trigger phrases in the `description` frontmatter field.
- Scripts should degrade gracefully on malformed input.
- When a skill mutates user state, apply changes only after explicit user approval.
- Use stdlib `unittest` for tests. Run from the script's directory: `cd <plugin>/scripts && python3 -m unittest test_*.py`
