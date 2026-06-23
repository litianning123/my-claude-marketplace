#!/usr/bin/env python3
"""
Hook Doctor — inspect and repair Claude Code hook configurations.

Usage:
    python3 doctor.py [--project DIR] [--root DIR] [--apply]

Scans installed plugin hooks and settings.json files for 7 common
misconfiguration patterns. Pass --apply to fix the 2 auto-fixable ones
(unquoted path variables and non-executable scripts).
"""

import argparse
import sys
from pathlib import Path

import sources
import checks
import fixer


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Inspect and repair Claude Code hook configurations")
    p.add_argument(
        "--project", type=str, default=None,
        help="Project to inspect (default: current directory)")
    p.add_argument(
        "--root", type=str, default=None,
        help="Scan only this directory tree for hooks.json (skips settings.json)")
    p.add_argument(
        "--apply", action="store_true",
        help="Write fixes (without this flag, report only)")
    return p.parse_args()


def _gather_sources(args: argparse.Namespace) -> tuple[list[sources.HookSource], str]:
    """Collect all hook sources and a human-readable scope description."""
    if args.root:
        root = Path(args.root).expanduser()
        project = Path(args.project).expanduser() if args.project else None
        plugin_files = sources.find_plugin_hooks(root)
        hook_sources = [sources.HookSource(f, project) for f in plugin_files]
        return hook_sources, f"plugin hooks under {root}"

    project = Path(args.project).expanduser() if args.project else Path.cwd()
    return sources.discover_sources(project), f"effective hooks for {project}"


def _group_by_file(findings: list) -> dict[str, list]:
    """Group findings by their file path."""
    grouped: dict[str, list] = {}
    for f in findings:
        grouped.setdefault(f.file, []).append(f)
    return grouped


def _print_report(findings: list) -> None:
    """Print findings grouped by file."""
    by_file = _group_by_file(findings)
    fixable_count = sum(1 for f in findings if f.fixable)
    report_count = len(findings) - fixable_count

    print(f"\nFound {len(findings)} problem(s) in {len(by_file)} file(s) "
          f"({fixable_count} fixable, {report_count} report-only):\n")

    for file_path, file_findings in by_file.items():
        print(file_path)
        for f in file_findings:
            tag = "FIXABLE" if f.fixable else "REPORT"
            loc = f.event or "—"
            print(f"  [{f.check}] [{tag}] {loc}: {f.command or '(no command)'}")
            print(f"      {f.detail}")
        print()


def main() -> int:
    args = _parse_args()
    hook_sources, scope = _gather_sources(args)
    print(f"Scanning {len(hook_sources)} hook-config file(s) — {scope}",
          file=sys.stderr)

    # Phase 1: Scan
    all_findings: list = []
    for hs in hook_sources:
        all_findings.extend(checks.scan_file(hs.path, hs.project_dir))

    if not all_findings:
        print("No hook configuration problems found.")
        return 0

    # Phase 2: Report
    _print_report(all_findings)

    if not args.apply:
        print("Dry run — re-run with --apply to fix auto-fixable items "
              "(this edits installed plugin files). Report-only items "
              "need manual attention.")
        return 0

    # Phase 3: Fix
    by_file = _group_by_file(all_findings)
    quoted = sum(fixer.fix_unquoted_vars(Path(p)) for p in by_file)
    chmodded = sum(
        1 for f in all_findings
        if f.check == "not_executable" and fixer.fix_executable(f)
    )

    # Phase 4: Verify — re-scan fixed files
    remaining = 0
    for hs in hook_sources:
        remaining += len(checks.scan_file(hs.path, hs.project_dir))

    print(f"Quoted {quoted} command(s); chmod +x on {chmodded} script(s). "
          f"Remaining problems: {remaining} "
          f"(report-only items are not auto-fixed).")
    print("Note: these are local edits to installed plugins. "
          "Push upstream or submit a PR to persist.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
