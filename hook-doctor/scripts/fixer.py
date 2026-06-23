#!/usr/bin/env python3
"""Fix application — safe, idempotent repairs for hook config problems."""

import json
import re
from pathlib import Path


# Regex mirrors checks.py — unquoted ${CLAUDE_*} path tokens
_UNQUOTED_VAR_RE = re.compile(
    r'(?<!")(\$\{(?:CLAUDE_PLUGIN_ROOT|CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_DATA)\}[^\s"]*)'
)


def quote_path_vars(command: str) -> str:
    """Wrap unquoted ${CLAUDE_*} path tokens in double quotes. Idempotent."""
    return _UNQUOTED_VAR_RE.sub(r'"\1"', command)


def _iter_handlers(data: dict):
    """Yield (event, handler) for every command-type hook handler."""
    for event, blocks in (data.get("hooks") or {}).items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            for h in (block.get("hooks", []) if isinstance(block, dict) else []):
                if isinstance(h, dict):
                    yield event, h


def fix_unquoted_vars(file_path: Path) -> int:
    """Apply quote fixes to one hooks/settings file.

    Walks every handler's 'command' field, wraps unquoted ${CLAUDE_*}
    tokens in double quotes. Re-validates JSON before writing.
    Already-quoted tokens are skipped (idempotent).

    Returns the number of commands changed. Returns 0 on parse failure.
    """
    path = Path(file_path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return 0

    # Collect old->new replacements
    replacements: dict[str, str] = {}
    for _event, handler in _iter_handlers(data):
        cmd = handler.get("command")
        if isinstance(cmd, str):
            new_cmd = quote_path_vars(cmd)
            if new_cmd != cmd:
                replacements[cmd] = new_cmd

    if not replacements:
        return 0

    # Apply replacements surgically via JSON-encoded string matching
    new_raw = raw
    for old, new in replacements.items():
        # Replace the JSON-encoded form to avoid matching substrings
        new_raw = new_raw.replace(json.dumps(old), json.dumps(new))

    # Validate before writing
    json.loads(new_raw)
    path.write_text(new_raw, encoding="utf-8")
    return len(replacements)


def fix_executable(finding) -> bool:
    """Add the execute bit for a not_executable finding. Refuses symlinks.

    The finding's 'detail' field contains the script path after
    'needs chmod +x: '. Re-checks that the file exists, is a regular
    file, and is not a symlink before modifying permissions.

    Returns True on success, False on refusal or error.
    """
    # Extract path from detail string — handles both
    # "Script is not executable (needs chmod +x): /path" (checks.py)
    # and "needs chmod +x: /path" (test/direct) formats
    detail = finding.detail
    idx = detail.rfind("needs chmod +x")
    if idx == -1:
        return False

    # Find the ": " separator that follows the description
    sep = detail.find(": ", idx)
    if sep == -1:
        return False

    script_path = detail[sep + 2:].strip()
    p = Path(script_path)

    # Safety gates
    if not p.exists():
        return False
    if p.is_symlink():
        return False
    if not p.is_file():
        return False

    # Add user/group/other execute bits
    p.chmod(p.stat().st_mode | 0o111)
    return True
