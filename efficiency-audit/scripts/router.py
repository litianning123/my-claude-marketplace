#!/usr/bin/env python3
"""CLAUDE.md routing — detect which files exist and route recommendations with data-driven scope decisions.

Decision matrix (from references/claude-md-routing.md):

    Files Present              Behavior
    ────────────               ────────
    Only global exists         Route there directly — no prompt
    Only project exists        Route there directly — no prompt
    Both exist                 Show A/B prompt, wait for user choice
    Neither exists             Ask which to create before proceeding

Scope recommendation signals:

    Signal                     Recommendation
    ──────                     ──────────────
    3+ distinct projects       Global (~/.claude/CLAUDE.md)
    ≥70% matches in one repo   Project (.claude/CLAUDE.md or root)
    2–3 projects, no dominant  No strong recommendation — ask user
    Personal/project-agnostic  Global (commit habits, tone preferences)

Scope exclusions (routed elsewhere, not through standard CLAUDE.md logic):

    Target / Category          Handler
    ─────────────────          ───────
    settings.json, hook-doctor hookify:configure or hook-doctor skill
    Terminal-title findings    references/terminal-title-check.md
    Karpathy guardrails merge  User-selected target (Phase 5)
    File bloat remediation     Determined by which file exceeds threshold
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ── Data types ──────────────────────────────────────────────────────────────────

@dataclass
class RouteTarget:
    """Where a recommendation should be written."""
    path: Path
    label: str          # e.g. "global (~/.claude/CLAUDE.md)" or "project (.claude/CLAUDE.md)"
    level: str          # "global", "project", "needs_decision", "needs_creation", "excluded"
    recommended: str | None = None       # "global" or "project" — router's recommendation
    reasoning: str = ""                  # why this target was chosen
    project_distribution: dict[str, int] = field(default_factory=dict)  # for A/B prompts
    needs_confirmation: bool = False     # True when user MUST confirm before writing


@dataclass
class FilePresence:
    """Which CLAUDE.md files exist on the filesystem (with verified existence)."""
    global_path: Path
    project_dot_claude_path: Path
    project_root_path: Path
    global_exists: bool = False
    project_dot_claude_exists: bool = False
    project_root_exists: bool = False

    @property
    def any_project_exists(self) -> bool:
        return self.project_dot_claude_exists or self.project_root_exists

    @property
    def best_project_path(self) -> Path:
        """Pick the best existing project file; prefer .claude/CLAUDE.md over root CLAUDE.md.
        If neither exists, return .claude/CLAUDE.md as the default creation target."""
        if self.project_dot_claude_exists:
            return self.project_dot_claude_path
        if self.project_root_exists:
            return self.project_root_path
        return self.project_dot_claude_path  # default — may not exist yet

    @property
    def case(self) -> str:
        """Which routing case applies: 'global_only', 'project_only', 'both', 'neither'."""
        if self.global_exists and self.any_project_exists:
            return "both"
        if self.global_exists:
            return "global_only"
        if self.any_project_exists:
            return "project_only"
        return "neither"


# ── File detection ──────────────────────────────────────────────────────────────

def detect_file_presence(project_dir: Path | None = None) -> FilePresence:
    """Check which CLAUDE.md files actually exist on the filesystem.

    Unlike the old detect_claude_md_files(), this verifies existence at call time
    and returns a rich FilePresence object with all paths and boolean flags.
    """
    pd = Path(project_dir) if project_dir else Path.cwd()
    gp = Path.home() / ".claude" / "CLAUDE.md"
    pdc = pd / ".claude" / "CLAUDE.md"
    pr = pd / "CLAUDE.md"
    return FilePresence(
        global_path=gp,
        project_dot_claude_path=pdc,
        project_root_path=pr,
        global_exists=gp.exists(),
        project_dot_claude_exists=pdc.exists(),
        project_root_exists=pr.exists(),
    )


# ── Project distribution extraction ─────────────────────────────────────────────

def _get(rec, key: str, default=None):
    """Unified accessor for Recommendation dataclass or plain dict."""
    if isinstance(rec, dict):
        return rec.get(key, default)
    return getattr(rec, key, default)


def extract_project_distributions(
    recommendations: list,
    findings: dict | None = None,
) -> dict[int, dict[str, int]]:
    """For each recommendation (keyed by list index), compute project_name → match_count.

    Uses raw findings when available (more accurate). Falls back to parsing
    evidence strings: "corrections: 5x across 3 sessions in my-repo".
    """
    distributions: dict[int, dict[str, int]] = {}

    # Path A: use raw findings data (most accurate)
    if findings:
        # Build a lookup: category → [(project, count), ...]
        for cat in ("corrections", "missing_context", "slow_start_context",
                     "automation_candidates", "git_workflow_errors", "tool_failures"):
            for group in findings.get(cat, []):
                proj = _get(group, "top_project", "")
                count = _get(group, "count", 0)
                if not proj:
                    continue
                # Match this finding group to its recommendation(s) by pattern overlap
                pattern = _get(group, "pattern", "")
                for i, rec in enumerate(recommendations):
                    evidence = _get(rec, "evidence", "")
                    if pattern and pattern in evidence:
                        distributions.setdefault(i, {}).setdefault(proj, 0)
                        distributions[i][proj] += count

    # Path B: parse evidence strings (fallback)
    for i, rec in enumerate(recommendations):
        if i in distributions:
            continue  # already populated from findings
        evidence = _get(rec, "evidence", "")
        # Format: "corrections: 5x across 3 sessions in my-repo"
        # or "tool_failures: Read/unread_write — 3x across 2 sessions"
        parts = evidence.split(" in ")
        if len(parts) > 1:
            proj = parts[-1].strip().rstrip(".")
            # Skip special markers
            if proj and proj not in ("?", "unknown", "this project"):
                distributions[i] = {proj: 1}
            else:
                distributions[i] = {}
        else:
            distributions[i] = {}

    return distributions


# ── Scope recommendation engine ─────────────────────────────────────────────────

# Categories that are inherently project-agnostic (always recommend global)
GLOBAL_BY_DEFAULT = {"hook_errors", "tool_failures"}

# Targets that bypass CLAUDE.md routing entirely (handled by other systems)
EXCLUDED_TARGETS = {"settings.json", "hook-doctor"}


def recommend_scope(
    rec,
    rec_index: int = 0,
    project_distributions: dict | None = None,
    file_presence: FilePresence | None = None,
) -> tuple[str, str, str]:
    """Determine the recommended scope for a recommendation.

    Returns (scope, reasoning, strength) where:
      scope  = "global" | "project" | "excluded"
      reasoning = human-readable explanation
      strength  = "strong" | "weak" | "none"

    Data-driven thresholds:
      - 3+ distinct projects → strong global
      - ≥70% of matches in one repo → strong project
      - 2–3 projects, no dominant → weak (no strong recommendation)
    """
    category = _get(rec, "category", "")
    target = _get(rec, "target", "CLAUDE.md")
    scope_from_synth = _get(rec, "scope", "global")

    # ── Exclusion checks ────────────────────────────────────────────────
    if target in EXCLUDED_TARGETS:
        handlers = {"settings.json": "hookify:configure", "hook-doctor": "hook-doctor skill"}
        handler = handlers.get(target, target)
        return "excluded", f"target is {target} — route to {handler} instead", "none"

    # ── Global-by-default categories ────────────────────────────────────
    if category in GLOBAL_BY_DEFAULT:
        return "global", "applies across all projects (not repo-specific)", "strong"

    # ── Data-driven recommendation ──────────────────────────────────────
    dist = (project_distributions or {}).get(rec_index, {})
    if not dist:
        # No project data — fall back to synthesizer scope hint
        if scope_from_synth == "project":
            evidence = _get(rec, "evidence", "")
            parts = evidence.split(" in ")
            proj = parts[-1].strip().rstrip(".") if len(parts) > 1 else "this project"
            return "project", f"all matches in {proj} (from synthesizer)", "weak"
        return "global", "no project-specific signal detected", "weak"

    distinct_projects = len(dist)
    total_matches = sum(dist.values())
    top_project, top_count = max(dist.items(), key=lambda kv: kv[1]) if dist else ("?", 0)
    concentration = top_count / total_matches if total_matches > 0 else 0

    # Signal 1: broad cross-project pattern → global
    if distinct_projects >= 3:
        return (
            "global",
            f"seen across {distinct_projects} projects — looks like a general habit",
            "strong",
        )

    # Signal 2: heavily concentrated in one repo → project
    if concentration >= 0.70 and distinct_projects >= 1:
        return (
            "project",
            f"{top_count}/{total_matches} matches ({concentration:.0%}) in {top_project} — repo-specific",
            "strong",
        )

    # Signal 3: 2–3 projects, no dominant → ambiguous
    if 2 <= distinct_projects <= 3:
        return (
            "global",
            f"seen in {distinct_projects} projects but no dominant concentration — weak preference for global",
            "weak",
        )

    # Signal 4: thin data, single project
    return (
        "project" if distinct_projects == 1 else "global",
        f"{total_matches} match(es) in {distinct_projects} project(s)",
        "weak",
    )


# ── Target resolution ───────────────────────────────────────────────────────────

def resolve_targets(
    recommendations: list,
    findings: dict | None = None,
    project_dir: Path | None = None,
) -> list[tuple]:
    """Resolve the target file for each recommendation.

    Args:
        recommendations: list of Recommendation objects from synthesizer.generate()
        findings: optional raw findings dict for accurate project-distribution counting
        project_dir: project root directory (defaults to cwd)

    Returns:
        list of (recommendation, RouteTarget, reasoning) tuples.
        The caller MUST handle needs_decision and needs_creation levels
        by prompting the user before writing.
    """
    fp = detect_file_presence(project_dir)
    distributions = extract_project_distributions(recommendations, findings)
    results = []

    for i, rec in enumerate(recommendations):
        scope, reasoning, strength = recommend_scope(rec, i, distributions, fp)

        # ── Excluded targets ────────────────────────────────────────────
        if scope == "excluded":
            target_name = _get(rec, "target", "CLAUDE.md")
            handler_map = {
                "settings.json": "hookify:configure",
                "hook-doctor": "hook-doctor skill",
            }
            target = RouteTarget(
                path=Path("."),  # not used
                label=f"EXCLUDED — route to {handler_map.get(target_name, target_name)}",
                level="excluded",
                reasoning=reasoning,
            )

        # ── Project scope (single project, or strong concentration) ─────
        elif scope == "project":
            if fp.case == "neither":
                # No files exist — ask which to create
                target = RouteTarget(
                    path=fp.best_project_path,
                    label=f"NEEDS CREATION: project ({fp.best_project_path})",
                    level="needs_creation",
                    recommended="project",
                    reasoning=reasoning,
                    project_distribution=distributions.get(i, {}),
                    needs_confirmation=True,
                )
            elif fp.case == "global_only":
                # Only global exists — route there but note the scope conflict
                target = RouteTarget(
                    path=fp.global_path,
                    label=f"project-scoped → global (~/.claude/CLAUDE.md) — no project file exists",
                    level="global",
                    recommended="project",
                    reasoning=f"{reasoning} (routed to global — no project file exists; create a project CLAUDE.md to scope this locally)",
                    project_distribution=distributions.get(i, {}),
                )
            else:
                # Project file exists (or both exist)
                target = RouteTarget(
                    path=fp.best_project_path,
                    label=f"project ({fp.best_project_path})",
                    level="project",
                    recommended="project",
                    reasoning=reasoning,
                    project_distribution=distributions.get(i, {}),
                )
                # If both exist, user must confirm project scope isn't silently overriding global
                if fp.case == "both":
                    target.needs_confirmation = True

        # ── Global scope ────────────────────────────────────────────────
        elif scope == "global":
            if fp.case == "both":
                # Both exist — user MUST confirm writing to global
                strength_label = "STRONG" if strength == "strong" else "WEAK"
                target = RouteTarget(
                    path=fp.global_path,
                    label=f"NEEDS DECISION [{strength_label} → global]: "
                          f"global (~/.claude/CLAUDE.md) or project",
                    level="needs_decision",
                    recommended="global",
                    reasoning=reasoning,
                    project_distribution=distributions.get(i, {}),
                    needs_confirmation=True,
                )
            elif fp.case == "global_only":
                target = RouteTarget(
                    path=fp.global_path,
                    label="global (~/.claude/CLAUDE.md)",
                    level="global",
                    recommended="global",
                    reasoning=reasoning,
                    project_distribution=distributions.get(i, {}),
                )
            elif fp.case == "project_only":
                # Global scope but only project file exists — route to project
                target = RouteTarget(
                    path=fp.best_project_path,
                    label=f"project ({fp.best_project_path}) — only project file exists",
                    level="project",
                    recommended="global",  # router thinks global, but only project available
                    reasoning=f"{reasoning} (routed to project — no global file exists)",
                    project_distribution=distributions.get(i, {}),
                )
            else:  # neither exists
                target = RouteTarget(
                    path=fp.global_path,
                    label="NEEDS CREATION: global (~/.claude/CLAUDE.md)",
                    level="needs_creation",
                    recommended="global",
                    reasoning=reasoning,
                    project_distribution=distributions.get(i, {}),
                    needs_confirmation=True,
                )

        results.append((rec, target, reasoning))

    return results


# ── Display formatting ──────────────────────────────────────────────────────────

def print_routing_table(resolved: list[tuple]) -> str:
    """Generate a routing summary table for terminal display.

    Rows are grouped by level: confirmed targets first, then needs_decision,
    then needs_creation, then excluded.
    """
    if not resolved:
        return "\n--- ROUTING ---\n  (no recommendations to route)"

    # Group by level for cleaner display
    order = {"global": 0, "project": 1, "needs_decision": 2, "needs_creation": 3, "excluded": 4}
    sorted_resolved = sorted(resolved, key=lambda x: order.get(x[1].level, 99))

    lines = ["\n─── ROUTING ───"]
    current_section = None

    for rec, target, reasoning in sorted_resolved:
        # Section headers
        section = target.level
        if section != current_section:
            current_section = section
            section_labels = {
                "global": "✓ Confirmed — Global",
                "project": "✓ Confirmed — Project",
                "needs_decision": "⚠ Needs Decision (both global & project exist)",
                "needs_creation": "⚠ Needs Creation (no CLAUDE.md exists yet)",
                "excluded": "↳ Excluded (handled separately)",
            }
            lines.append(f"\n  {section_labels.get(section, section.upper())}:")

        rule_preview = _get(rec, "proposed_rule", "")[:100]
        confidence = _get(rec, "confidence", "?")
        lines.append(f"    [{confidence}] {rule_preview}")
        lines.append(f"    → {target.label}")
        lines.append(f"      Why: {target.reasoning}")

        # Show project distribution when available
        dist = target.project_distribution
        if dist and len(dist) > 1:
            proj_summary = ", ".join(f"{p}: {c}" for p, c in dist.items())
            lines.append(f"      Projects: {proj_summary}")

    # Count summary
    counts = Counter(t.level for _, t, _ in sorted_resolved)
    summary_parts = []
    for level, label in [("global", "global"), ("project", "project"),
                          ("needs_decision", "need decision"),
                          ("needs_creation", "need creation"),
                          ("excluded", "excluded")]:
        if counts[level]:
            summary_parts.append(f"{counts[level]} {label}")
    lines.append(f"\n  Summary: {', '.join(summary_parts)}")

    return "\n".join(lines)


def format_ab_prompt(needs_decision: list[tuple]) -> str:
    """Generate a structured A/B prompt for recommendations needing user scope choice.

    Follows the upstream format: shows options A and B with ← recommended annotations,
    "Seen in:" project distribution, and the mandatory global-write warning.

    Returns a string the agent should present verbatim to the user.
    """
    if not needs_decision:
        return ""

    lines = [
        "",
        "─── Scope Decision Required ───",
        "",
        "Both ~/.claude/CLAUDE.md (global) and a project CLAUDE.md exist.",
        "⚠️  Writing to ~/.claude/CLAUDE.md affects EVERY future session across ALL projects.",
        "",
    ]

    for i, (rec, target, reasoning) in enumerate(needs_decision, 1):
        rule = _get(rec, "proposed_rule", "")
        dist = target.project_distribution
        recommended = target.recommended or "global"

        lines.append(f"**Rule {i}:** {rule}")
        lines.append("")

        # Build project distribution display
        if dist and len(dist) > 1:
            project_list = ", ".join(f"{p} ({c})" for p, c in dist.items())
            lines.append(f"  Seen in: {project_list}")
        elif dist:
            proj_name = list(dist.keys())[0]
            lines.append(f"  Seen in: {proj_name} ({dist[proj_name]} matches)")

        # Show options
        if recommended == "global":
            lines.append("  A) Global (~/.claude/CLAUDE.md) ← recommended")
            lines.append(f"     ({target.reasoning})")
            lines.append("  B) Project (this repo only)")
        else:
            lines.append("  A) Global (~/.claude/CLAUDE.md)")
            lines.append("  B) Project (this repo only) ← recommended")
            lines.append(f"     ({target.reasoning})")

        lines.append("")

    lines.extend([
        "Reply with the rule number and choice (e.g., '1A, 2B'),",
        "or 'all A', 'all B', or 'skip 2'.",
    ])

    return "\n".join(lines)


def format_checklist(approved: list[tuple]) -> str:
    """Generate annotated checklist entries with target-file annotations.

    Format: `[ ] (scope: project_name → file_path) rule_text`

    Example output:
        [ ] (project: dd-trace-js → .claude/CLAUDE.md) NEVER commit without explicit instruction
        [ ] (global → ~/.claude/CLAUDE.md) ALWAYS verify git context before running commands
    """
    if not approved:
        return "(no rules to apply)"

    lines = ["\n─── Checklist ───"]
    for rec, target, _reasoning in approved:
        rule = _get(rec, "proposed_rule", "")

        # Build the scope annotation
        if target.level == "global":
            annotation = "global → ~/.claude/CLAUDE.md"
        elif target.level == "project":
            # Try to extract project name from distribution
            dist = target.project_distribution
            proj_name = list(dist.keys())[0] if dist else "this project"
            annotation = f"project: {proj_name} → {target.path}"
        elif target.level == "excluded":
            annotation = f"excluded → {target.label}"
        else:
            annotation = target.label

        lines.append(f"  [ ] ({annotation}) {rule}")

    return "\n".join(lines)


# ── Legacy compatibility wrappers ───────────────────────────────────────────────

def detect_claude_md_files(project_dir: Path | None = None) -> dict[str, Path | None]:
    """Legacy wrapper — returns raw Path dict without existence checking.
    Prefer detect_file_presence() for new code.
    """
    fp = detect_file_presence(project_dir)
    return {
        "global": fp.global_path,
        "project_dot_claude": fp.project_dot_claude_path,
        "project_root": fp.project_root_path,
    }
