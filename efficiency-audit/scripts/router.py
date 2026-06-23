#!/usr/bin/env python3
"""CLAUDE.md routing — detect which files exist and route recommendations appropriately."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RouteTarget:
    """Where a recommendation should be written."""
    path: Path
    label: str          # e.g. "global (~/.claude/CLAUDE.md)" or "project (.claude/CLAUDE.md)"
    level: str          # "global" or "project"


def detect_claude_md_files(project_dir: Path | None = None) -> dict[str, Path | None]:
    """Detect which CLAUDE.md files exist on the system.

    Returns dict with keys: 'global', 'project_dot_claude', 'project_root'.
    Values are Path if the file exists, None otherwise.
    """
    project_dir = Path(project_dir) if project_dir else Path.cwd()
    return {
        "global": Path.home() / ".claude" / "CLAUDE.md",
        "project_dot_claude": project_dir / ".claude" / "CLAUDE.md",
        "project_root": project_dir / "CLAUDE.md",
    }


def count_projects(recommendations: list) -> dict[str, int]:
    """Count how many distinct projects each recommendation is seen in.

    Extracts project info from the recommendation's evidence field.
    Returns {rec_index: project_count}.
    """
    project_counts = {}
    for i, rec in enumerate(recommendations):
        evidence = getattr(rec, 'evidence', '')
        # Evidence format: "corrections: 5x across 3 sessions in my-repo"
        parts = evidence.split(" in ")
        if len(parts) > 1:
            project = parts[-1].strip()
            project_counts[i] = 1 if project == "?" else 1
    return project_counts


def recommend_scope(rec, project_counts: dict[str, int] | None = None) -> tuple[str, str]:
    """Determine the recommended scope for a recommendation.

    Returns (scope, reasoning) where scope is "global" or "project".
    """
    rec_scope = getattr(rec, 'scope', 'global')
    rec_category = getattr(rec, 'category', '')

    # Settings.json and hook-doctor targets are always global
    target = getattr(rec, 'target', 'CLAUDE.md')
    if target in ("settings.json", "hook-doctor"):
        return "global", f"target is {target} — not a CLAUDE.md rule"

    # If the synthesizer already set project scope and we have top_project data, honor it
    if rec_scope == "project":
        evidence = getattr(rec, 'evidence', '')
        parts = evidence.split(" in ")
        proj = parts[-1].strip() if len(parts) > 1 else "this project"
        return "project", f"all matches in {proj}"

    # Tool failures and hook errors are usually global patterns
    if rec_category in ("tool_failures", "hook_errors"):
        return "global", "applies across all projects"

    return "global", "no project-specific signal"


def resolve_targets(recommendations: list, project_dir: Path | None = None) -> list[tuple]:
    """Resolve the target file for each recommendation.

    Returns list of (recommendation, RouteTarget, reasoning) tuples.
    Does NOT write anything — caller decides what to do with the routing info.
    """
    files = detect_claude_md_files(project_dir)
    project_dir = Path(project_dir) if project_dir else Path.cwd()

    has_global = files["global"].exists() if files["global"] else False
    has_project = (files["project_dot_claude"].exists() if files["project_dot_claude"] else False) or \
                  (files["project_root"].exists() if files["project_root"] else False)

    # Pick the best project-level file
    project_file = files["project_dot_claude"] if (files["project_dot_claude"] and files["project_dot_claude"].exists()) else \
                   files["project_root"] if (files["project_root"] and files["project_root"].exists()) else \
                   project_dir / ".claude" / "CLAUDE.md"  # default — may not exist yet

    results = []
    for rec in recommendations:
        rec_scope, reasoning = recommend_scope(rec)

        if rec_scope == "project":
            # Project-specific → route to project file
            target = RouteTarget(
                path=project_file,
                label=f"project ({project_file})",
                level="project",
            )
        elif has_global and not has_project:
            # Only global file exists → route there silently
            target = RouteTarget(
                path=files["global"],
                label="global (~/.claude/CLAUDE.md)",
                level="global",
            )
        elif has_project and not has_global:
            # Only project file exists → route there
            target = RouteTarget(
                path=project_file,
                label=f"project ({project_file})",
                level="project",
            )
        else:
            # Both exist → flag for user decision
            target = RouteTarget(
                path=files["global"],  # tentative — user picks
                label="NEEDS DECISION: global (~/.claude/CLAUDE.md) or project",
                level="needs_decision",
            )

        results.append((rec, target, reasoning))

    return results


def print_routing_table(resolved: list[tuple]) -> str:
    """Generate a routing table for the text report or agent display."""
    lines = ["\n--- ROUTING ---"]
    for rec, target, reasoning in resolved:
        rule_preview = getattr(rec, 'proposed_rule', '')[:80]
        lines.append(f"  [{target.level}] {target.label}")
        lines.append(f"    Rule: {rule_preview}...")
        lines.append(f"    Why: {reasoning}")
    return "\n".join(lines)
