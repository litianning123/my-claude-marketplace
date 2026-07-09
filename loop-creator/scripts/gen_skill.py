#!/usr/bin/env python3
"""
Tier 3 generator — produces a reusable SKILL.md + reference implementation.

Produces:
  generate_skill_md(goal, trigger_phrases, description, operating_procedure) -> str
  generate_reference_implementation(...) -> dict[str, str]
"""

from textwrap import dedent
from gen_project import generate_all_project_files


def _slugify(text: str) -> str:
    """Convert a goal string into a slug suitable for a skill name."""
    return text.lower().strip().replace(" ", "-")


def _indent(text: str, prefix: str = "    ") -> str:
    """Indent each non-empty line of text with prefix."""
    return "\n".join(prefix + line for line in text.split("\n"))


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
    name = _slugify(goal)

    desc = description.strip() if description.strip() else f"Automated skill for: {goal}"
    triggers = trigger_phrases.strip()
    if triggers:
        desc += f" Trigger phrases: {triggers}"

    title = goal.strip().title() + " Skill"

    procedure_indented = _indent(operating_procedure.strip())

    return dedent(f"""\
    ---
    name: {name}
    description: "{desc}"
    ---

    # {title}

    {procedure_indented}
    """)


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

    project_files = generate_all_project_files(answers)

    prefixed = {}
    for filename, content in project_files.items():
        prefixed[f"reference-implementation/{filename}"] = content

    return prefixed
