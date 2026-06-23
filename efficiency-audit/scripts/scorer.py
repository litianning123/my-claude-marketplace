#!/usr/bin/env python3
"""File efficiency scorer — piecewise linear interpolation for config file bloat."""

import json
import os
import subprocess
from pathlib import Path

CONTROL_POINTS: list[tuple[int, float]] = [
    (0, 1.00), (300, 1.00), (750, 0.50), (5000, 0.00),
]
P_ZERO = 5000
RECIPE_BOOK_THRESHOLD = 200


def efficiency_score(lines: int) -> float:
    """Return efficiency score in [0.0, 1.0] via piecewise linear interpolation."""
    if lines >= P_ZERO:
        return 0.0
    for i in range(len(CONTROL_POINTS) - 1):
        x0, y0 = CONTROL_POINTS[i]
        x1, y1 = CONTROL_POINTS[i + 1]
        if x0 <= lines <= x1:
            t = (lines - x0) / (x1 - x0) if x1 != x0 else 0.0
            return round(y0 + t * (y1 - y0), 4)
    return 0.0


def diagnosis(score: float) -> str:
    if score == 0.0:
        return "Critical Context Blocker"
    if score >= 0.90:
        return "Optimal"
    if score >= 0.70:
        return "Good"
    if score >= 0.50:
        return "Warning — consider trimming"
    return "Critical — significant bloat"


def recipe_book_alert(lines: int) -> bool:
    return lines > RECIPE_BOOK_THRESHOLD


def score_file(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    lines = len(text.splitlines())
    score = efficiency_score(lines)
    return {
        "path": str(path),
        "lines": lines,
        "bytes": len(text.encode("utf-8")),
        "score": score,
        "diagnosis": diagnosis(score),
        "recipe_book_alert": recipe_book_alert(lines),
    }


def score_files(paths: list[Path]) -> list[dict]:
    return [r for p in paths if (r := score_file(p)) is not None]


def resolve_memory_path() -> Path | None:
    """Resolve the project MEMORY.md path, honoring autoMemoryDirectory."""
    for p in [
        Path.home() / ".claude" / "settings.json",
        Path(".claude/settings.json"),
        Path(".claude/settings.local.json"),
    ]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if "autoMemoryDirectory" in d:
                return Path(os.path.expanduser(d["autoMemoryDirectory"])) / "MEMORY.md"
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = os.getcwd()
    proj = root.replace("/", "-").replace(".", "-")
    return Path.home() / ".claude" / "projects" / proj / "memory" / "MEMORY.md"
