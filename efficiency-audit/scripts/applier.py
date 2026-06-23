#!/usr/bin/env python3
"""Marker-block writer — idempotent CLAUDE.md rule application."""

from datetime import datetime, timezone
from pathlib import Path

MARKER_START = "<!-- efficiency-audit:start -->"
MARKER_END = "<!-- efficiency-audit:end -->"


def read_block(file_path: Path) -> list[str]:
    """Extract rules from an existing marker block. Returns empty list if no block found."""
    if not file_path.exists():
        return []
    text = file_path.read_text(encoding="utf-8")
    start = text.find(MARKER_START)
    end = text.find(MARKER_END)
    if start == -1 or end == -1 or end <= start:
        return []
    inner = text[start + len(MARKER_START):end]
    return [line.strip()[2:] for line in inner.splitlines()
            if line.strip().startswith("- ")]


def _build_block(rules: list[str], timestamp: str) -> str:
    lines = [MARKER_START,
             f"<!-- Last updated: {timestamp} by efficiency-audit skill -->",
             ""]
    if rules:
        lines.append("## Efficiency Audit Rules")
        lines.append("")
        for rule in rules:
            lines.append(f"- {rule}")
    else:
        lines.append("<!-- No rules approved yet -->")
    lines.append("")
    lines.append(MARKER_END)
    return "\n".join(lines)


def write_block(file_path: Path, rules: list[str]) -> str:
    """Write or replace the marker block. Returns 'replace' or 'append'."""
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = _build_block(rules, timestamp)

    start = text.find(MARKER_START)
    end = text.find(MARKER_END)
    if start != -1 and end != -1 and end > start:
        before = text[:start].rstrip("\n")
        after = text[end + len(MARKER_END):].lstrip("\n")
        parts = [before, block]
        if after:
            parts.append(after)
        new_text = "\n\n".join(parts) + "\n"
        action = "replace"
    else:
        new_text = text.rstrip("\n") + "\n\n" + block + "\n"
        action = "append"

    file_path.write_text(new_text, encoding="utf-8")
    return action


def preview_diff(file_path: Path, rules: list[str]) -> str:
    """Return a human-readable diff preview without writing."""
    existing = read_block(file_path)
    removed = [r for r in existing if r not in rules]
    added = [r for r in rules if r not in existing]
    kept = [r for r in existing if r in rules]
    lines = [f"File: {file_path}", f"Rules: {len(existing)} → {len(rules)}", ""]
    for r in kept:
        lines.append(f"  - {r}")
    for r in removed:
        lines.append(f"- - {r}  [removed]")
    for r in added:
        lines.append(f"+ - {r}  [new]")
    return "\n".join(lines)
