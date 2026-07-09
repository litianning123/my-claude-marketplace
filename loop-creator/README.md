# Loop Creator

A Claude Code plugin that helps you design and generate loop configurations through a guided interview. 

## What it does

- Interviews you about your automation goal (what repeats? how do you verify? when should it stop?)
- Recommends the right output format (command, project folder, or reusable skill)
- Generates ready-to-use loop configurations with safety boundaries, verification checklists, and scheduling instructions

## Installation

Copy the `loop-creator/` directory into your Claude Code plugins directory.

## Usage

Invoke with phrases like:
- "Create a loop for my daily standup"
- "Set up a CI monitoring loop"
- "I want to automate my weekly code review"

The wizard will guide you through readiness check, scope definition, and scheduling — then generate the right files for your needs.

## Output Tiers

| Tier | What you get | Best for |
|------|-------------|----------|
| Command | A ready-to-paste `/loop` command | Simple polling, stateless checks |
| Project | A complete loop workspace (TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, outputs/) | Stateful, multi-step workflows |
| Skill | A reusable SKILL.md + reference implementation | Team workflows, recurring patterns |
