---
name: loop-creator
description: "Use when the user wants to create a Claude Code loop, set up recurring automation, schedule a repeated task, build a /loop command, create a polling workflow, or design any agentic loop. Trigger phrases: 'create a loop', 'set up a loop', 'build a loop', 'automate this to run', 'schedule this task', 'make this recurring', 'I want a loop for', 'design a loop', '/loop creator'."
---

# Loop Creator

A wizard that interviews users about their automation goal and generates ready-to-run Claude Code loop configurations.

## Core Principle

**A loop is not just a repeated prompt. It needs: trigger, context, action, verification, state update, and decision.** This wizard encodes loop engineering best practices — readiness check, permission ladder, maker-checker verification, and manual-before-scheduled discipline.

## Flow

1. Interview user (three phases, one question at a time)
2. Run tier detector script to score answers
3. Present tier recommendation with reasoning — wait for user confirmation
4. Generate output using the matching generator script
5. Write files (for tiers 2-3) or present command (for tier 1)
6. ALWAYS include manual test instructions before scheduling advice

---

## Phase 1: Readiness Gate

Ask one question at a time. If any answer is too vague, push back with a suggestion to narrow scope. The goal is to filter out "bad first loops" early.

### Q1: "What task should this loop do? Describe it in one sentence."

Wait for answer. If the answer is broad ("improve my codebase" / "clean my computer"), push back:
"That's a big scope. A good first loop does one specific, checkable thing. Can we narrow this to one concrete action? For example: 'review the project folder and write a daily summary' rather than 'improve the codebase.'"

### Q2: "How often should this run? (e.g., every 30 minutes, daily, every PR, on file change)"

Wait for answer. Convert to a cadence string for later use (e.g., "every morning" → "24h", "every 30 min" → "30m").

### Q3: "How would you verify the output is correct? What would make you say 'this run was good' vs 'this needs fixing'?"

Wait for answer. If vague ("it should look right"), probe: "Can we make that more concrete? For example: 'the report has all required sections' or 'tests pass' or 'the file exists at the expected path.'"

### Q4: "What does Claude need access to? (e.g., just this folder, git history, GitHub issues, CI logs)"

Wait for answer. This determines context breadth and external tool needs.

### Q5: "When should this loop stop or escalate to you? What's the stop condition?"

Wait for answer. If vague ("when it's done"), push back: "Let's define a concrete stop condition. For example: 'stop after writing the report and updating state' or 'escalate if the same error appears twice.'"

### Q6: "What's the worst that could happen if the loop gets it wrong?"

Wait for answer. Map to permission level:
- "Nothing, it's read-only" → Level 1
- "It could write a bad report" → Level 2
- "It could modify the wrong file" → Level 3
- "It could post something public" → Level 4+

## Phase 2: Scope & Shape

### Q7: "Walk me through one iteration. What should Claude do, step by step?"

Wait for answer. Extract:
- Inputs: what files/APIs/data Claude reads
- Actions: inspect, summarize, classify, draft, fix, notify
- Outputs: where results go

### Q8: "Does each run need to remember what happened in previous runs?"

If yes → stateful, needs PROGRESS.md.
If no → stateless, each run is independent.

### Q9: "Is this just for you, or should others on your team be able to reuse it?"

If team reuse → flag for tier detection (+2 reusable bonus).

## Phase 3: Cadence & Autonomy

### Q10: "What permission level feels right to start?"

Present options derived from Q6 risk answer:
1. Read-only — inspects and reports, changes nothing
2. Draft output — writes reports/plans to an outputs/ folder
3. Sandbox edits — modifies files only in an isolated workspace
4. Human-approved writes — drafts actions, human approves before applying

### Q11: "Should this run on a fixed schedule (every morning), or should it self-pace (check, then decide when to check again)?"

If fixed → cron-based `/loop 24h`
If self-paced → dynamic `/loop` (no interval)

---

## Tier Detection

After all questions, build an answers dict and run the detector:

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from tier_detector import detect_tier

answers = {
    'multi_step': <true|false>,
    'stateful': <true|false>,
    'external_tools': <true|false>,
    'human_review': <true|false>,
    'complex_verification': <true|false>,
    'reusable': <true|false>,
}
tier, reasoning = detect_tier(answers)
print(json.dumps({'tier': tier, 'reasoning': reasoning}))
"
```

Parse the JSON output. Present to user:
"Based on your answers: {reasoning}. I recommend the **{tier}** tier. Sound good?"

Wait for confirmation. If user says no, ask which tier they'd prefer.

---

## Output Generation

### Tier 1: Command

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_command import generate_command, generate_manual_test_reminder

cmd = generate_command(
    goal='<goal>',
    cadence='<cadence>',
    context='<context>',
    action='<action>',
    stop_condition='<stop>',
    verify='<verify>',
    risk='<risk>',
)
print(cmd)
print()
print(generate_manual_test_reminder())
"
```

Present the command and reminder to the user. No files are written.

### Tier 2: Project

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_project import generate_all_project_files

answers = {
    'goal': '<goal>',
    'scope': '<scope>',
    'expected_output': '<expected_output>',
    'action': '<action>',
    'verify': '<verify>',
    'safety': '<safety>',
    'cadence': '<cadence>',
    'stop': '<stop>',
    'initial_status': '<initial_status>',
    'output_name': '<output_name>',
}
files = generate_all_project_files(answers)
print(json.dumps(files))
"
```

Parse the JSON. Ask user where to create the project folder. Write each file using the Write tool.

Then present the manual test prompt:
```
Run the <goal> loop for this workspace.

Follow LOOP_INSTRUCTIONS.md exactly.
Before acting, read TASK.md and PROGRESS.md.
Do not modify any files except the allowed output paths.
```

And the scheduling command:
```
/loop <cadence> Run the <goal> loop. Follow LOOP_INSTRUCTIONS.md exactly.
```

### Tier 3: Skill

First, generate the project files (same as Tier 2) as the reference implementation.

Then generate the SKILL.md:

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_skill import generate_skill_md, generate_reference_implementation

skill = generate_skill_md(
    goal='<goal>',
    trigger_phrases='<triggers>',
    description='<description>',
    operating_procedure='<procedure>',
)
print('===SKILL===')
print(skill)
print('===END_SKILL===')
"
```

Write the SKILL.md and reference implementation files. Tell the user where to place the skill (their skills directory).

---

## Hard Rules

1. **NEVER recommend scheduling without manual test instructions.** Every output must include a "run this manually first" section.
2. **NEVER auto-select a tier.** Always present the reasoning and ask for confirmation.
3. **Push back on vague answers.** If the user's task sounds like a "bad first loop" (vague, high-risk, unverifiable), say so and help them narrow scope.
4. **The permission ladder is non-negotiable.** If a user wants full automation on first loop, recommend starting at Level 1-2 and earning more autonomy.
5. **Scripts are for generation only.** Never use them to write files directly — you (the agent) control all Write operations after user approval.
