---
name: loop-creator
description: "Use when the user wants to create a Claude Code loop, set up recurring automation, schedule a repeated task, build a /loop command, create a polling workflow, or design any agentic loop. Trigger phrases: 'create a loop', 'set up a loop', 'build a loop', 'automate this to run', 'schedule this task', 'make this recurring', 'I want a loop for', 'design a loop', '/loop creator'."
---

# Loop Creator

Wizard that interviews users and generates ready-to-run loop configurations. Encodes loop engineering best practices: readiness check, permission ladder, maker-checker verification, and manual-before-scheduled discipline.

**Core principle:** A loop is not just a repeated prompt. It needs: trigger → context → action → verification → state update → decision.

## Flow

1. Interview user (three phases, one question at a time) — push back on vague answers
2. Run tier detector script → present reasoning → wait for user confirmation
3. Generate output using the matching generator script
4. Write files (tiers 2-3) or present command (tier 1)
5. ALWAYS include manual test instructions before scheduling advice

## Interview Questions

Ask one at a time. Push back if answers are vague or sound like a "bad first loop" (broad, high-risk, unverifiable). Map answers to variables using the table in the next section.

### Phase 1: Readiness Gate

| # | Question | Guidance |
|---|----------|----------|
| Q1 | What task should this loop do? (one sentence) | Push back on broad answers like "improve my codebase." Narrow to one concrete, checkable action. |
| Q2 | How often should this run? (e.g., 30m, daily, per PR, on file change) | Convert to cadence string: "every morning" → `24h`, "every 30 min" → `30m`. |
| Q3 | How would you verify the output is correct? What makes a run "good" vs "needs fixing"? | Push back on vague: "it should look right." Probe for concrete: "report has all sections," "tests pass," "file exists at expected path." |
| Q4 | What does Claude need access to? (folder, git history, GitHub, CI logs) | Determines context breadth and `external_tools` flag. |
| Q5 | When should this loop stop or escalate? What's the stop condition? | Push back on "when it's done." Concrete: "stop after writing report + updating state" or "escalate if same error appears twice." |
| Q6 | What's the worst that could happen if the loop gets it wrong? | Maps to permission level: "nothing, read-only" → L1; "bad report" → L2; "modify wrong file" → L3; "post something public" → L4+. |

### Phase 2: Scope & Shape

| # | Question | Guidance |
|---|----------|----------|
| Q7 | Walk me through one iteration. What should Claude do, step by step? | Extract: inputs (files/APIs/data), actions (inspect/summarize/classify/draft/fix/notify), outputs (where results go). |
| Q8 | Does each run need to remember what happened in previous runs? | Yes → stateful (needs PROGRESS.md). No → stateless. |
| Q9 | Is this just for you, or should others on your team reuse it? | Team reuse → +2 reusable bonus in tier detection. |

### Phase 3: Cadence & Autonomy

| # | Question | Guidance |
|---|----------|----------|
| Q10 | What permission level feels right to start? | Present options: (1) Read-only, (2) Draft output to outputs/, (3) Sandbox edits, (4) Human-approved writes. Derive default from Q6 risk. |
| Q11 | Fixed schedule (every morning) or self-paced (check, then decide when to check again)? | Fixed → cron `/loop 24h`. Self-paced → dynamic `/loop` (no interval). |

## Answer-to-Parameter Mapping

| Q | Variable | Tier 1 (cmd) | Tier 2 (project) | Tier 3 (skill) |
|---|----------|-------------|-------------------|----------------|
| Q1 | `goal` | `goal` | `goal` | `goal` |
| Q2 | `cadence` | `cadence` | `cadence` | — |
| Q3 | `verify` | `verify` | `verify` | — |
| Q4 | `context` | `context` | — | — |
| Q5 | `stop` | `stop_condition` | `stop` | — |
| Q6 | `risk` | `risk` | — | — |
| Q7 | `action` | `action` | `action` | `operating_procedure` |
| Q8 | `stateful` | — | encoded in answers dict | — |
| Q9 | `reusable` | — | — | if true → tier 3 |
| Q10 | — | embedded in `safety` | `safety` | embedded in SKILL.md |
| Q11 | — | embedded in `cadence` | embedded in `cadence` | — |

## Tier Detection

Build answers dict from Q4/Q8/Q9 (binary flags) and Q1/Q5/Q3 (complexity signals):

- `multi_step`: true if Q7 describes 3+ distinct actions
- `stateful`: true if Q8 = yes
- `external_tools`: true if Q4 mentions anything beyond local files
- `human_review`: true if Q6 risk ≥ L2
- `complex_verification`: true if Q3 mentions tests, schemas, or multi-check
- `reusable`: true if Q9 = team reuse

Run the detector using the invocation in `references/script-invocations.md` (Tier Detection section). Parse JSON. Present reasoning and wait for user confirmation. Never auto-select.

## Output Generation

**Escaping:** Before substituting user answers, escape `"` → `\"` and `\` → `\\`.

**All invocation blocks** are in `references/script-invocations.md`. Load that file when generating output.

### Tier 1: Command

Use the "Tier 1: Command" block. Present the command + manual test reminder to user. No files written.

### Tier 2: Project

Use the "Tier 2: Project" block. Ask user where to create the project folder. Write each file. Present the manual test prompt and scheduling command.

### Tier 3: Skill

First, generate project files (same Tier 2 block) as reference. Then use the "Tier 3: Skill" block. Write SKILL.md + reference implementation. Tell user where to place the skill.

## Hard Rules

1. **NEVER recommend scheduling without manual test instructions.**
2. **NEVER auto-select a tier.** Present reasoning, ask for confirmation.
3. **Push back on vague answers.** Flag bad first loops early and help narrow scope.
4. **The permission ladder is non-negotiable.** Recommend L1-2 for first loops.
5. **Scripts are for generation only.** Agent controls all file writes after user approval.
