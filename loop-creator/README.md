# Loop Creator

[中文](README.zh-CN.md)

A Claude Code plugin that helps you design and generate loop configurations through a guided interview. 

## What it does

- Interviews you about your automation goal (what repeats? how do you verify? when should it stop?)
- Recommends the right output format (command, project folder, or reusable skill)
- Generates ready-to-use loop configurations with safety boundaries, verification checklists, and scheduling instructions

## Installation

Copy the `loop-creator/` directory into your Claude Code plugins directory.

## Quick Start

Invoke with phrases like:
- "Create a loop for my daily standup"
- "Set up a CI monitoring loop"
- "I want to automate my weekly code review"

The wizard will guide you through readiness check, scope definition, and scheduling — then generate the right files for your needs.

## Step-by-Step Usage

### 1. Start the wizard

Say one of the trigger phrases above. The wizard begins Phase 1 — the Readiness Gate.

### 2. Answer the 11 questions

The wizard asks one question at a time across three phases:

**Phase 1: Readiness Gate (Q1-Q6)** — Filters out "bad first loops" early.
- Q1: What task should this loop do?
- Q2: How often should it run?
- Q3: How would you verify the output?
- Q4: What does Claude need access to?
- Q5: When should it stop or escalate?
- Q6: What's the worst that could happen if it goes wrong?

If your answer is too vague, the wizard pushes back and helps you narrow scope.

**Phase 2: Scope & Shape (Q7-Q9)** — Defines what each iteration does.
- Q7: Walk through one iteration step by step
- Q8: Does each run need to remember previous runs?
- Q9: Is this for you, or should your team reuse it?

**Phase 3: Cadence & Autonomy (Q10-Q11)** — Nails down scheduling and permissions.
- Q10: What permission level should it start with?
- Q11: Fixed schedule or self-paced?

### 3. Review the tier recommendation

The wizard scores your answers and recommends an output tier:

> Based on your answers: Score 4 — multi-step workflow, stateful, requires human review gate, complex verification. Recommended: a project folder with TASK.md, LOOP_INSTRUCTIONS.md, and PROGRESS.md. Sound good?

Confirm or choose a different tier.

### 4. Review the generated output

The wizard generates your loop configuration. For project/skill tiers, it asks where to save files before writing anything.

### 5. Run manually first (mandatory)

Every output includes a "run this manually before scheduling" section. Run the loop by hand 3-5 times, inspect the outputs, and tighten the instructions before scheduling.

### 6. Schedule

Once the manual runs are stable, use the `/loop` command included in the output to schedule it.

## Output Tiers

| Tier | What you get | Best for |
|------|-------------|----------|
| Command | A ready-to-paste `/loop` command | Simple polling, stateless checks |
| Project | A complete loop workspace (TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, outputs/) | Stateful, multi-step workflows |
| Skill | A reusable SKILL.md + reference implementation | Team workflows, recurring patterns |

See `references/example-outputs.md` for concrete examples of each tier.
