#!/usr/bin/env python3
"""
Tier 3 generator — produces a reusable SKILL.md + reference implementation.

Produces:
  generate_skill_md(goal, trigger_phrases, description, operating_procedure) -> str
  generate_reference_implementation(...) -> dict[str, str]
"""

import re
from gen_project import generate_all_project_files


def _derive_skill_name(goal: str) -> str:
    """Derive a kebab-case skill name from the goal string."""
    goal = (goal or "").strip()
    name = goal.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def generate_skill_md(
    goal: str,
    trigger_phrases: str,
    description: str,
    operating_procedure: str,
) -> str:
    """Generate a complete SKILL.md with YAML frontmatter and body.

    Args:
        goal: Short name for the skill (e.g. "Automated PR review").
        trigger_phrases: Comma-separated trigger phrases that activate the skill.
        description: A one-line description of what the skill does.
        operating_procedure: The step-by-step procedure for the agent to follow.

    Returns:
        Complete SKILL.md content as a string.
    """
    name = _derive_skill_name(goal)
    triggers = trigger_phrases or goal.lower()

    return f"""\
---
name: {name}
description: "Use when {description}. Trigger phrases: {triggers}."
---

# {goal.title()}

## Overview
A repeatable loop for: {goal}.

## When to Use
- When the user asks for: {triggers}
- When the task repeats on a schedule
- When the output can be verified against a checklist

## File Structure
Create this workspace before the first run:

```
<loop-name>/
├── TASK.md
├── LOOP_INSTRUCTIONS.md
├── PROGRESS.md
└── outputs/
    └── <output-file>.md
```

Templates for each file are in the reference implementation.

## Operating Procedure
{operating_procedure}

## Verification Checklist
Before ending the run, verify:
- Output file exists
- All required sections are present
- PROGRESS.md was updated
- No files outside allowed paths were modified

## Safety Rules
- Do not delete, rename, or move files
- Do not modify source files
- Only write to the explicitly allowed output paths
- Mark anything uncertain for human review

## Manual Before Scheduled
Run the loop manually 3-5 times before scheduling. Check:
- Output is useful and concise
- State file is updated correctly
- Safety boundaries are respected
- Verification passes consistently

## Scheduling
Once manual runs are stable:
```
/loop <cadence> Run the {goal} loop. Follow LOOP_INSTRUCTIONS.md exactly.
```

## Common Mistakes
- Scheduling before manual testing
- Skipping state file update at end of run
- Letting output grow too verbose
- Forgetting to check verification before marking done
- Treating first successful run as proof of reliability

## Reference
See `reference-implementation/` for a complete working example.
"""


def generate_reference_implementation(
    goal: str,
    scope: str,
    expected_output: str,
    action: str,
    verify: str,
    safety: str,
    cadence: str,
    stop: str,
    initial_status: str,
    output_name: str,
) -> dict[str, str]:
    """Generate a reference implementation as a project folder.

    Uses generate_all_project_files from gen_project.py to produce
    TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, and an output file.
    All filenames are prefixed with 'reference-implementation/'.

    Args:
        goal: The automation goal.
        scope: What the loop is allowed to do.
        expected_output: Path to the expected output file.
        action: What the loop should do each run.
        verify: Verification checklist (markdown lines).
        safety: Safety rules (markdown lines).
        cadence: How often the loop runs.
        stop: Stop conditions.
        initial_status: Initial PROGRESS.md status.
        output_name: The name of the output file (e.g. "report.md").

    Returns:
        dict mapping 'reference-implementation/...' filenames to content strings.
    """
    answers = {
        "goal": goal,
        "scope": scope,
        "expected_output": expected_output,
        "action": action,
        "verify": verify,
        "safety": safety,
        "cadence": cadence,
        "stop": stop,
        "initial_status": initial_status,
        "output_name": output_name,
    }

    files = generate_all_project_files(answers)
    return {f"reference-implementation/{k}": v for k, v in files.items()}
