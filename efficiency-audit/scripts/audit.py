#!/usr/bin/env python3
"""
Efficiency Audit — analyze Claude Code transcripts for workflow inefficiencies.

Usage:
    python3 audit.py [--days N] [--project P] [--output json|text] [--apply]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import scanner
import patterns
from patterns import CATEGORY_ORDER, CATEGORY_LABELS
import synthesizer
import applier
import scorer
import router


def _parse_args():
    p = argparse.ArgumentParser(
        description="Analyze Claude Code conversations for efficiency patterns")
    p.add_argument("--days", type=int, default=30,
                   help="Scan conversations from last N days (default: 30)")
    p.add_argument("--project", type=str, default=None,
                   help="Restrict to a project (substring match)")
    p.add_argument("--output", choices=["json", "text"], default="text",
                   help="Output format (default: text)")
    p.add_argument("--apply", action="store_true",
                   help="Write approved rules to target files")
    return p.parse_args()


def _finding_group_to_dict(fg) -> dict:
    """Convert a FindingGroup (or dict) to a plain dict for JSON serialization."""
    if isinstance(fg, dict):
        return fg
    return {
        "pattern": fg.pattern,
        "category": fg.category,
        "count": fg.count,
        "sessions": fg.sessions,
        "top_project": fg.top_project,
        "examples": fg.examples,
        "preceding_action": fg.preceding_action,
    }


def _summary_to_dict(summary: dict) -> dict:
    """Convert summary (which may contain Counter) to JSON-safe dict."""
    out = {}
    for k, v in summary.items():
        if isinstance(v, Counter):
            out[k] = dict(v.most_common(50))
        else:
            out[k] = v
    return out


def _findings_to_json(findings: dict, deltas: dict, recs: list) -> dict:
    """Build a JSON-safe output dict from findings, deltas, and recommendations."""
    out = {}
    out["summary"] = _summary_to_dict(findings.get("summary", {}))

    # Convert FindingGroup lists
    for cat in CATEGORY_ORDER:
        out[cat] = [_finding_group_to_dict(g) for g in findings.get(cat, [])]

    # tool_failures and hook_errors are already dicts
    out["tool_failures"] = findings.get("tool_failures", [])
    out["hook_errors"] = findings.get("hook_errors", [])

    out["deltas"] = deltas
    out["recommendations"] = [
        {"proposed_rule": r.proposed_rule,
         "estimated_tokens_saved": r.estimated_tokens_saved,
         "scope": r.scope,
         "target": r.target,
         "evidence": r.evidence,
         "confidence": r.confidence,
         "category": r.category}
        for r in recs
    ]
    return out


def _print_text_report(findings: dict, deltas: dict, recs: list):
    s = findings["summary"]
    print("=== Claude Code Efficiency Audit ===")
    print(f"Sessions analyzed: {s['sessions_analyzed']}")
    print(f"User messages: {s['total_user_messages']}")
    dr = s["date_range"]
    earliest = dr["earliest"][:10] if dr.get("earliest") else "N/A"
    latest = dr["latest"][:10] if dr.get("latest") else "N/A"
    print(f"Date range: {earliest} -> {latest}")
    projects = s.get("projects", {})
    if projects:
        if isinstance(projects, Counter):
            proj_disp = dict(projects.most_common(5))
        else:
            proj_disp = projects
        if proj_disp:
            print(f"Projects: {proj_disp}")
    print()

    for key in CATEGORY_ORDER:
        groups = findings[key]
        total = sum(g.count if hasattr(g, 'count') else g.get("count", 0) for g in groups)
        if not total:
            continue
        title = CATEGORY_LABELS.get(key, key.upper())
        header = f"--- {title} ({total} matches across {len(groups)} patterns)"
        # Wire up deltas: show trend vs baseline
        d = deltas.get(key)
        if d and d.get("previous", 0) > 0 and d.get("pct_change") is not None:
            direction = "↓" if d["delta"] < 0 else ("↑" if d["delta"] > 0 else "→")
            header += f", was {d['previous']}, {d['pct_change']:+d}% {direction}"
        header += " ---"
        print(header)
        for g in groups[:5]:
            count = g.count if hasattr(g, 'count') else g.get("count", 0)
            sessions = g.sessions if hasattr(g, 'sessions') else g.get("sessions", 1)
            examples = g.examples if hasattr(g, 'examples') else g.get("examples", [])
            proj = g.top_project if hasattr(g, 'top_project') else g.get("top_project", "")
            proj_str = f" ({proj})" if proj else ""
            ex = examples[0][:140] if examples else "?"
            print(f"    [{count}x / {sessions} sessions{proj_str}] e.g. {ex}")
            pa = g.preceding_action if hasattr(g, 'preceding_action') else g.get("preceding_action")
            if key == "corrections" and pa:
                print(f"      Claude did: {pa[:120]}")
        print()

    tf = findings.get("tool_failures", [])
    if tf:
        total = sum(g.get("count", 0) for g in tf)
        print(f"--- TOOL FAILURES ({total} total) ---")
        for g in tf[:5]:
            print(f"    [{g['tool']}/{g['error_category']}] {g['count']}x / {g['sessions']} sessions")

    he = findings.get("hook_errors", [])
    if he:
        print(f"\n--- HOOK ERRORS ({len(he)} unique) ---")
        for h in he[:5]:
            print(f"    [{h.get('hook_name', '?')}] exit={h.get('exit_code')}")

    if recs:
        print(f"\n--- RECOMMENDATIONS ({len(recs)}) ---")
        for i, r in enumerate(recs[:10], 1):
            print(f"  {i}. [{r.confidence}] [{r.target}] ~{r.estimated_tokens_saved} tokens saved")
            print(f"     {r.proposed_rule[:150]}")
        print()

        # Route each recommendation to the right CLAUDE.md
        resolved = router.resolve_targets(recs)
        print(router.print_routing_table(resolved))

    # Scorer output
    claude_paths = [
        Path.home() / ".claude" / "CLAUDE.md",
        Path(".claude/CLAUDE.md"),
        Path("CLAUDE.md"),
    ]
    for p in claude_paths:
        if p.exists():
            result = scorer.score_file(p)
            if result:
                print(f"  CLAUDE.md ({p}): {result['lines']} lines, "
                      f"score={result['score']:.2f} ({result['diagnosis']})")
                if result["recipe_book_alert"]:
                    print(f"    Recipe Book remediation recommended (>200 lines)")


def main():
    args = _parse_args()

    # Phase 1: Scan
    files = scanner.find_transcript_files(args.days, args.project)
    print(f"Scanning {len(files)} transcript file(s) from last {args.days} days...",
          file=sys.stderr)

    baseline = patterns.load_baseline(args.project)
    sessions = scanner.parse_all(files)
    print(f"Parsed {len(sessions)} session(s) with activity", file=sys.stderr)

    findings = patterns.analyze(sessions)
    deltas = patterns.compute_deltas(findings, baseline)

    # Phase 2: Synthesize
    recs = synthesizer.generate(findings)

    # Phase 3: Report
    if args.output == "json":
        out = _findings_to_json(findings, deltas, recs)
        print(json.dumps(out, indent=2))
    else:
        _print_text_report(findings, deltas, recs)

    # Save baseline for next run
    patterns.save_baseline(findings, args.project)

    # Phase 4: Apply (if requested)
    if args.apply and recs:
        resolved = router.resolve_targets(recs)

        # Group rules by target file
        by_target: dict[Path, list[str]] = {}
        hook_recs = []
        for rec, target, reasoning in resolved:
            target_name = getattr(rec, 'target', 'CLAUDE.md')
            if target_name == "hook-doctor":
                hook_recs.append(rec)
            elif target.level == "needs_decision":
                # Both global and project exist — default to project (safer)
                project_file = Path(".claude/CLAUDE.md") if Path(".claude/CLAUDE.md").exists() else Path("CLAUDE.md")
                by_target.setdefault(project_file, []).append(getattr(rec, 'proposed_rule', ''))
            else:
                by_target.setdefault(target.path, []).append(getattr(rec, 'proposed_rule', ''))

        # Write per-target
        for target_path, rules in by_target.items():
            if rules:
                action = applier.write_block(target_path, rules)
                print(f"\nApplied {len(rules)} rule(s) to {target_path} ({action})")

        if hook_recs:
            print(f"\n{len(hook_recs)} hook-doctor recommendation(s) — run hook-doctor separately.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
