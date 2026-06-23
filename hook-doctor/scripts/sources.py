#!/usr/bin/env python3
"""Hook source discovery — finds all hook config files on the system."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class HookSource:
    """A hook configuration file and its project context."""
    path: Path
    project_dir: Path | None = None


def find_plugin_hooks(root: Path) -> list[Path]:
    """Find all hooks/hooks.json under root, deduplicated by resolved realpath."""
    if not root.is_dir():
        return []
    seen: set[Path] = set()
    out: list[Path] = []
    for f in sorted(root.rglob("hooks/hooks.json")):
        real = f.resolve()
        if real not in seen:
            seen.add(real)
            out.append(f)
    return out


def discover_sources(project_dir: Path | None = None) -> list[HookSource]:
    """Discover all hook configuration sources on the system.

    Scans three locations:
    1. User settings: ~/.claude/settings.json and settings.local.json
    2. Project settings: <project>/.claude/settings.json and settings.local.json
    3. Plugin hooks: ~/.claude/plugins/**/hooks/hooks.json

    Returns a list of HookSource objects. Gracefully handles missing directories.
    """
    resolved_project = project_dir.resolve() if project_dir else Path.cwd()
    sources: list[HookSource] = []

    # User-level settings
    for name in ("settings.json", "settings.local.json"):
        p = Path.home() / ".claude" / name
        if p.is_file():
            sources.append(HookSource(p, resolved_project))

    # Project-level settings
    for name in ("settings.json", "settings.local.json"):
        p = resolved_project / ".claude" / name
        if p.is_file():
            sources.append(HookSource(p, resolved_project))

    # Installed plugin hooks
    plugins_base = Path.home() / ".claude" / "plugins"
    for f in find_plugin_hooks(plugins_base):
        sources.append(HookSource(f, resolved_project))

    return sources
