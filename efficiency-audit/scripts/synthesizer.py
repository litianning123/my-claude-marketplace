#!/usr/bin/env python3
"""Heuristic rule engine — generates fix recommendations from findings without LLM dependency."""

from dataclasses import dataclass
import re


def _get(group, key: str, default=None):
    """Get a value from either a FindingGroup dataclass or a plain dict."""
    if isinstance(group, dict):
        return group.get(key, default)
    return getattr(group, key, default)


@dataclass
class Recommendation:
    proposed_rule: str
    estimated_tokens_saved: int
    scope: str
    target: str
    evidence: str
    confidence: str
    category: str


# Template definitions — category → (min_count, min_sessions, tokens_per, target, scope)
TEMPLATES = {
    "corrections":        (3, 2, 100, "CLAUDE.md", "project"),
    "missing_context":    (2, 3, 200, "CLAUDE.md", "project"),
    "slow_start_context": (2, 2, 150, "CLAUDE.md", "project"),
    "automation_candidates": (2, 2, 150, "settings.json", "project"),
    "git_workflow_errors": (2, 1, 200, "CLAUDE.md", "project"),
}


def _confidence(count: int, sessions: int) -> str:
    if count >= 5 or sessions >= 3:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def _build_rule(group, category: str, tokens_per: int) -> str:
    """Build a natural-language rule from a finding group."""
    count = _get(group, "count", 0)
    sessions = _get(group, "sessions", 1)
    proj = _get(group, "top_project", "unknown")
    examples = _get(group, "examples", [])
    example = examples[0] if examples else "(no example)"
    preceding = _get(group, "preceding_action", "")

    if category == "corrections":
        return (
            f"NEVER {_infer_action(preceding, example)}. "
            f"Found {count} correction(s) across {sessions} session(s) in {proj}. "
            f'Example: "{example}"'
        )
    elif category in ("missing_context", "slow_start_context"):
        return (
            f"ADD to CLAUDE.md: stable fact re-explained {count} times across {sessions} sessions in {proj}. "
            f'Example: "{example}"'
        )
    elif category == "automation_candidates":
        return (
            f"CONSIDER automation: recurring pattern detected {count} times across {sessions} sessions in {proj}. "
            f'Example: "{example}"'
        )
    elif category == "git_workflow_errors":
        return (
            f"ADD git workflow procedure to CLAUDE.md: stale-ref or cascade issue detected "
            f"{count} times across {sessions} sessions in {proj}. "
            f"Always reference LOCAL branch names, not origin/<branch>, in cascade commands. "
            f'Example: "{example}"'
        )
    return f"Investigate: {count} occurrences of '{group.get('pattern', '?')}' in {proj}"


def _infer_action(preceding: str, example: str) -> str:
    """Heuristic: extract the action verb from preceding_action or example text."""
    # Common patterns in Claude's preceding actions
    m = re.search(r'\b(commit\w*|wrote|added|created|deleted|changed|modified|pushed|merged)\b',
                  (preceding or "").lower())
    if m:
        action = m.group(1)
        return f"{action} without explicit instruction"
    # Fallback: look in the example
    m2 = re.search(r"don'?t\s+(\w+)", example.lower())
    if m2:
        return f"{m2.group(1)} without explicit instruction"
    return "act without explicit instruction"


def generate(findings: dict) -> list[Recommendation]:
    """Generate ranked recommendations from analysis findings."""
    recommendations = []

    # Process each finding category
    for category, (min_count, min_sessions, tokens_per, target, scope) in TEMPLATES.items():
        for group in findings.get(category, []):
            count = _get(group, "count", 0)
            sessions = _get(group, "sessions", 1)
            if count < min_count or sessions < min_sessions:
                continue
            scope_val = "project" if _get(group, "top_project") else "global"
            recommendations.append(Recommendation(
                proposed_rule=_build_rule(group, category, tokens_per),
                estimated_tokens_saved=count * tokens_per,
                scope=scope_val,
                target=target,
                evidence=f"{category}: {count}x across {sessions} sessions in {_get(group, 'top_project', '?')}",
                confidence=_confidence(count, sessions),
                category=category,
            ))

    # Hook errors → hook-doctor recommendation
    hook_errors = findings.get("hook_errors", [])
    if hook_errors:
        total_sessions = len(set(he.get("session_count", 1) for he in hook_errors))
        total_count = sum(he.get("session_count", 1) for he in hook_errors)
        recommendations.append(Recommendation(
            proposed_rule=(
                f"Run hook-doctor to scan all hook configs for static issues. "
                f"{len(hook_errors)} unique hook error(s) across ~{total_sessions} session(s). "
                f"Hook errors are configuration failures — not candidates for CLAUDE.md rules."
            ),
            estimated_tokens_saved=0,
            scope="global",
            target="hook-doctor",
            evidence=f"hook_errors: {len(hook_errors)} unique, {total_count} occurrences",
            confidence="medium",
            category="hook_errors",
        ))

    # Tool failures → CLAUDE.md prevention rules
    tool_failures = findings.get("tool_failures", [])
    for tf in tool_failures:
        count = tf.get("count", 0)
        sessions = tf.get("sessions", 1)
        if count < 2:
            continue
        category = tf.get("error_category", "unknown")
        tool = tf.get("tool", "?")
        rule_map = {
            "unread_write": f"ALWAYS Read a file before calling {tool} (Edit/Write) on it",
            "wrong_context": "VERIFY working directory and git context before running commands",
            "file_not_found": "VERIFY file paths exist before accessing them",
            "git_error": "VERIFY git repository state before running git commands",
            "bash_nonzero": "CHECK command exit codes and handle failures explicitly",
        }
        rule = rule_map.get(category, f"PREVENT {category} errors ({tool})")
        recommendations.append(Recommendation(
            proposed_rule=f"{rule}. Found {count} occurrence(s) across {sessions} session(s).",
            estimated_tokens_saved=count * 300,
            scope="global",
            target="CLAUDE.md",
            evidence=f"tool_failures: {tool}/{category} — {count}x across {sessions} sessions",
            confidence=_confidence(count, sessions),
            category="tool_failures",
        ))

    recommendations.sort(key=lambda r: r.estimated_tokens_saved, reverse=True)
    return recommendations
