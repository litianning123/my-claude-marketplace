# Loop Creator Plugin — Design Spec

**Date:** 2026-07-08
**Source:** Based on "How to Create Loops with Claude Code" by Youssef Hosni (levelup.gitconnected.com)
**Status:** Design approved, pending implementation plan

## Overview

A wizard-style Claude Code skill that interviews users about their automation goal and generates ready-to-run loop configurations. Encodes the loop engineering methodology from Youssef Hosni's article into a guided experience — from readiness check through tiered output generation.

## Architecture

### Plugin Structure

```
loop-creator/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── loop-creator/
│       └── SKILL.md              # Wizard orchestrator
├── scripts/
│   ├── gen_command.py            # Tier 1 output generator
│   ├── gen_project.py            # Tier 2 output generator
│   ├── gen_skill.py              # Tier 3 output generator
│   ├── tier_detector.py          # Heuristic tier scoring
│   └── test_*.py                 # Unit tests
└── README.md
```

**Key principle:** Scripts return content as strings — they never write files directly. The agent (following SKILL.md) controls all filesystem side effects. This keeps scripts unit-testable and gives the agent final say over file placement.

### Design Rationale

- Follows existing repo patterns (`efficiency-audit`, `quicknotes`) — SKILL.md as orchestrator, stdlib Python scripts for generation
- Scripts are independently testable with `unittest`
- SKILL.md stays lean; conversation logic lives in the skill, template rendering lives in scripts

## Interview Flow

Three phases, one question at a time:

### Phase 1: Readiness Gate

Maps to the article's Loop Readiness Check. If answers are too vague, the wizard pushes back (encodes the "bad first loops" warnings).

| Question | Detects |
|----------|---------|
| "Does this task repeat? How often?" | Trigger cadence |
| "How would you verify the output is correct?" | Checkability |
| "What does Claude need to read/access?" | Context breadth |
| "When should this loop stop or escalate?" | Stop condition clarity |
| "What's the worst that could happen if it gets it wrong?" | Risk level → permission ladder |

### Phase 2: Scope & Shape

Discovers what the loop does each iteration:
- Inputs (files, APIs, git log, etc.)
- Actions (summarize, classify, draft, fix, notify)
- Outputs (report file, PR comment, state update)
- Whether state needs to persist between runs

### Phase 3: Cadence & Autonomy

- Interval: polling (5m-30m), daily, weekly, or event-driven
- Permission level: read-only, draft-only, sandbox edits, human-approved writes
- Cron-based (`/loop 24h`) vs self-paced (dynamic `/loop`)

### Tier Detection Algorithm

```python
def detect_tier(answers: dict) -> tuple[str, str]:
    score = 0
    # +1 each: multi-step, stateful, external tools,
    #           human review gate, complex verification
    # +2: "I want to reuse this" or "my team needs this"
    
    if score <= 2: return ("command", "...")
    if score <= 4: return ("project", "...")
    return ("skill", "...")
```

The wizard recommends the tier with reasoning and asks for confirmation (heuristic + confirmation gate).

## Output Tiers

### Tier 1 — "Command"

A single `/loop` command, ready to paste. No files created.

```
/loop 30m Check CI status for PR #123. 
Read the latest CI run logs, classify the result, 
and notify me if it failed. Do not modify any code.
```

Comes with: "Run this manually once first" reminder.

### Tier 2 — "Project"

A complete loop workspace folder following the article's structure:

```
<loop-name>/
├── TASK.md                 # Goal + scope
├── LOOP_INSTRUCTIONS.md    # Operating procedure + verification + safety
├── PROGRESS.md             # State file (pre-populated)
└── outputs/
    └── <output-file>.md
```

Each file is generated from article templates, populated with user-specific answers. Includes manual test prompt and eventual `/loop` scheduling command.

### Tier 3 — "Skill"

A reusable SKILL.md + reference implementation:
- YAML frontmatter with `name` and `description` ("Use when...")
- Operating procedure adapted as skill body
- Tier 2 project files included as reference example
- Follows `writing-skills` conventions from this repo

### Hard Constraint (All Tiers)

The wizard never recommends scheduling without also outputting manual test instructions. Encodes the article's "manual before scheduled" discipline.

## Key Concepts Encoded from the Article

1. **Loop Readiness Check** (Section 2) → Phase 1 interview questions
2. **Permission Ladder** (6 levels) → Tier detection + Phase 3 autonomy questions
3. **File templates** (Sections 3-4) → Generation scripts
4. **Maker-Checker verification** (Section 5) → Embedded in every LOOP_INSTRUCTIONS.md
5. **Manual before scheduled** (Section 6) → Hard constraint in all tiers
6. **Draft-first pattern** (Section 7) → Encoded in permission boundaries
7. **Stop policy & iteration limits** (Section 6) → Embedded in generated instructions

## Non-Goals (v1)

- Does NOT execute or schedule loops itself — it generates configurations for the user to run
- Does NOT connect to external services — it generates instructions, not integrations
- Does NOT modify existing loops — it creates new ones from scratch
- Does NOT handle `/goal` (condition-based continuation) — v1 focuses on `/loop` (time-based)

## Testing Approach

Following the `writing-skills` TDD methodology:
1. **RED:** Run pressure scenarios with sub-agents WITHOUT the skill — document where they skip readiness checks, produce vague output, or jump straight to scheduling
2. **GREEN:** Write SKILL.md addressing those specific failures
3. **REFACTOR:** Close loopholes, test with varied loop requests
4. Scripts tested independently with `unittest`

## Files to Create

| File | Purpose |
|------|---------|
| `.claude-plugin/plugin.json` | Plugin manifest |
| `skills/loop-creator/SKILL.md` | Wizard orchestrator skill |
| `scripts/tier_detector.py` | Heuristic tier scoring |
| `scripts/gen_command.py` | Tier 1 output generator |
| `scripts/gen_project.py` | Tier 2 output generator |
| `scripts/gen_skill.py` | Tier 3 output generator |
| `scripts/test_tier_detector.py` | Unit tests |
| `scripts/test_gen_command.py` | Unit tests |
| `scripts/test_gen_project.py` | Unit tests |
| `scripts/test_gen_skill.py` | Unit tests |
| `README.md` | Human-facing documentation |
