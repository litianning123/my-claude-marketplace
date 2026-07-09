#!/usr/bin/env python3
"""
Tier detector — scores interview answers to recommend output tier.

Returns (tier_name, reasoning_string) where tier_name is one of:
"command", "project", "skill".
"""


def detect_tier(answers: dict) -> tuple[str, str]:
    """
    Score interview answers and return (tier, reasoning).

    Scoring:
        +1 each: multi_step, stateful, external_tools,
                 human_review, complex_verification
        +2: reusable ("I want to reuse this" / "my team needs this")

    Thresholds (without reusable override):
        score <= 2  ->  "command"  (simple, stateless, single-run)
        score <= 4  ->  "project"  (stateful, multi-step, needs files)
        score >  4  ->  "skill"    (reusable, complex, team-facing)

    Reusable always promotes to skill regardless of score.
    """
    score = 0
    factors = []

    checks = [
        ("multi_step", "multi-step workflow"),
        ("stateful", "stateful (needs persistence between runs)"),
        ("external_tools", "uses external tools/connectors"),
        ("human_review", "requires human review gate"),
        ("complex_verification", "complex verification (tests, schema, multi-check)"),
    ]

    for key, label in checks:
        if answers.get(key):
            score += 1
            factors.append(label)

    is_reusable = answers.get("reusable", False)
    if is_reusable:
        score += 2
        factors.append("marked as reusable across projects/teams")

    if is_reusable:
        tier = "skill"
        tier_label = "a reusable SKILL.md + reference implementation"
    elif score <= 2:
        tier = "command"
        tier_label = "a single run /loop command"
    elif score <= 4:
        tier = "project"
        tier_label = "a project folder with TASK.md, LOOP_INSTRUCTIONS.md, and PROGRESS.md"
    else:
        tier = "skill"
        tier_label = "a reusable SKILL.md + reference implementation"

    reasoning = _build_reasoning(tier_label, score, factors)
    return tier, reasoning


def _build_reasoning(tier_label: str, score: int, factors: list[str]) -> str:
    """Build a human-readable reasoning string."""
    factor_text = ", ".join(factors) if factors else "no complexity factors detected"
    return (
        f"Score {score} — {factor_text}. "
        f"Recommended: {tier_label}."
    )
