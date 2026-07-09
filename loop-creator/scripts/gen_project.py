#!/usr/bin/env python3
"""
Tier 2 generator -- produces a complete loop project folder.

Generates: TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, outputs/<name>.md
Following the article's templates from Sections 3-4.
"""

from textwrap import dedent


def generate_task_md(goal: str, scope: str, expected_output: str) -> str:
    """Generate TASK.md content."""
    safe_scope = scope
    if "not modify" not in safe_scope.lower() and "should not" not in safe_scope.lower():
        safe_scope += (
            "\nClaude should not modify source files, delete files, rename files, "
            "move files, send messages, open tickets, or interact with external "
            "systems during this first version of the loop."
        )

    return dedent(f"""\
    # {goal.title()} Loop

    ## Goal
    {goal}

    ## Expected Output
    Each run should produce or update:
    {expected_output}

    ## Scope
    {safe_scope}
    """)


def generate_loop_instructions_md(
    action_steps: str,
    verify_checklist: str,
    safety_rules: str,
    cadence: str,
    stop_policy: str,
) -> str:
    """Generate LOOP_INSTRUCTIONS.md content."""
    cadence_section = _cadence_section(cadence)

    return dedent(f"""\
    # Loop Instructions

    You are running a {cadence} loop.

    ## Before You Start
    1. Read `TASK.md`.
    2. Read `PROGRESS.md`.
    3. Inspect the relevant context for this run.
    4. Identify what changed, what is incomplete, and what needs human review.

    ## What You Should Do
    {action_steps}

    After completing the action, update `PROGRESS.md` with:
    - Date of this run
    - Summary of what happened
    - Files or areas checked
    - Output produced
    - What the next run should do
    - Anything that needs human review

    ## Safety Rules
    {safety_rules}
    - If you are unsure whether an action is allowed, stop and ask for human review.

    {cadence_section}

    ## Verification Checklist
    Before ending the run, verify the following:
    {verify_checklist}

    ### Safety Boundary
    Only the files explicitly listed above may be modified.
    If any other file was modified, stop and report the issue.

    ## Failure Policy
    If verification fails:
    1. If the failure is a missing section or output, fix it once.
    2. If `PROGRESS.md` was not updated, update it once.
    3. If any forbidden file was modified, stop immediately and report the issue.
    4. If the same verification check fails twice, stop and mark the run as needing human review.

    ## Stop Policy
    {stop_policy}
    """)


def _cadence_section(cadence: str) -> str:
    """Build the scheduled run policy section."""
    try:
        num = int("".join(c for c in cadence if c.isdigit()))
    except ValueError:
        num = 0
    unit = "".join(c for c in cadence if c.isalpha()).lower()

    is_testing = unit in ("m", "min", "minute", "minutes") and num <= 30

    testing_note = ""
    if is_testing:
        testing_note = (
            "\n**Note:** This is a short testing interval. "
            "Use it only to validate behavior. Move to the real cadence "
            "once the loop is stable.\n"
        )

    return dedent(f"""\
    ## Scheduled Run Policy
    When this loop runs on a schedule:{testing_note}
    - If there are meaningful changes, write a concise report.
    - If there are no meaningful changes, write a short "No meaningful changes" note.
    - If human review is needed, mark it clearly in `PROGRESS.md`.
    - If the same blocker appears in two consecutive runs, do not keep retrying. Escalate to human review.
    - If verification fails twice, stop and mark the run as not accepted.
    - Keep scheduled outputs short unless there is something important to report.
    - Do not create extra files unless explicitly allowed.
    """)


def generate_progress_md(goal: str, initial_status: str) -> str:
    """Generate PROGRESS.md content with starter template."""
    return dedent(f"""\
    # Loop Progress

    ## Current State
    - Status: {initial_status}
    - Main objective: {goal}
    - Current focus: Validate the loop manually before scheduling
    - Last updated:

    ## Last Run
    - Date:
    - Trigger:
    - Summary:
    - Files reviewed:
    - Output produced:

    ## Open Items
    -

    ## Blockers
    -

    ## Needs Human Review
    -

    ## Next Run Should
    - Read `TASK.md`, `PROGRESS.md`, and `LOOP_INSTRUCTIONS.md`.
    - Inspect the workspace.
    - Produce the expected output.
    - Update this file before stopping.

    ## Decisions Made
    - The loop starts with local file access only.
    - Scheduling should happen only after stable manual runs.

    ## Do Not Repeat
    - Do not modify source files.
    - Do not delete, rename, or move files.
    - Do not create extra files unless explicitly instructed.
    """)


def generate_output_starter(output_name: str) -> str:
    """Generate a starter output file."""
    base = output_name.replace(".md", "").replace("outputs/", "").replace("-", " ").title()
    return f"# {base}\n\nNo loop run has been completed yet.\n"


def generate_all_project_files(answers: dict) -> dict[str, str]:
    """Generate all project files from interview answers.

    Args:
        answers: dict with keys: goal, scope, expected_output, action,
                 verify, safety, cadence, stop, initial_status, output_name

    Returns:
        dict mapping filename -> content
    """
    goal = answers.get("goal", "Loop Task")
    scope = answers.get("scope", "Read and report only.")
    expected_output = answers.get("expected_output", "outputs/report.md")
    action = answers.get("action", "Inspect the workspace and produce output.")
    verify = answers.get("verify", "- Output file exists\n- Required sections present")
    safety = answers.get("safety", "- Do not delete files\n- Do not modify source files")
    cadence = answers.get("cadence", "24h")
    stop = answers.get("stop", "Stop after completing the action. Escalate if blocked.")
    initial_status = answers.get("initial_status", "Manual setup -- validate before scheduling")
    output_name = answers.get("output_name", "report.md")

    return {
        "TASK.md": generate_task_md(goal, scope, expected_output),
        "LOOP_INSTRUCTIONS.md": generate_loop_instructions_md(
            action, verify, safety, cadence, stop
        ),
        "PROGRESS.md": generate_progress_md(goal, initial_status),
        f"outputs/{output_name}": generate_output_starter(output_name),
    }
