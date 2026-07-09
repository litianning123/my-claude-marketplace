#!/usr/bin/env python3
"""
Tier 1 generator — produces a ready-to-paste /loop command.
"""


def generate_command(
    goal: str,
    cadence: str,
    context: str,
    action: str,
    stop_condition: str,
    verify: str,
    risk: str,
) -> str:
    """
    Generate a /loop command string from interview answers.

    Returns a multi-line string ready to paste into Claude Code.
    """
    safety_line = _safety_line(risk)
    cadence_note = _cadence_note(cadence)

    return (
        f"/loop {cadence} {goal}.\n"
        f"\n"
        f"Context: {context}\n"
        f"Action: {action}\n"
        f"Stop when: {stop_condition}\n"
        f"Verify: {verify}\n"
        f"{safety_line}"
        f"{cadence_note}"
    )


def _safety_line(risk: str) -> str:
    """Determine the safety boundary line based on risk level."""
    risk_lower = risk.lower()
    if "read-only" in risk_lower:
        return "Do not modify any code or files.\n"
    if "no code" in risk_lower and "change" not in risk_lower:
        return "Do not modify any code or files.\n"
    if "code" in risk_lower or "modif" in risk_lower:
        return "Only modify files explicitly listed above. Mark anything uncertain for human review.\n"
    return "If uncertain whether an action is safe, stop and mark for human review.\n"


def _cadence_note(cadence: str) -> str:
    """Add guidance for short polling intervals."""
    try:
        num = int("".join(c for c in cadence if c.isdigit()))
    except ValueError:
        return ""
    unit = "".join(c for c in cadence if c.isalpha()).lower()
    if unit in ("m", "min", "minute", "minutes") and num <= 30:
        return f"\n(This is a polling interval. The loop checks every {cadence} and reports only when something changed.)\n"
    return ""


def generate_manual_test_reminder() -> str:
    """Generate the mandatory manual-test-before-scheduling reminder."""
    return (
        "## Before scheduling\n"
        "Run this manually once first:\n"
        "1. Paste the command without `/loop <cadence>` into Claude Code\n"
        "2. Verify the output is correct\n"
        "3. Check that no unexpected files were modified\n"
        "4. Only then schedule with the full `/loop` command above\n"
    )
