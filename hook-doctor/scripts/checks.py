#!/usr/bin/env python3
"""Check engine — data model, protocol, and 7 static checks for hook configs."""

from dataclasses import dataclass, field
import json
import os
import re
import shlex
from pathlib import Path


# --- Data model -----------------------------------------------------------------

@dataclass
class Finding:
    """A detected problem in a hook configuration."""
    file: str
    event: str | None
    command: str | None
    check: str
    detail: str
    fixable: bool


@dataclass
class CheckContext:
    """Context passed to each check function."""
    file_path: Path
    plugin_root: Path | None
    project_dir: Path | None


# --- Recognized hook event names -------------------------------------------------

VALID_EVENTS: set[str] = {
    "SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PermissionRequest", "PermissionDenied", "PostToolUse",
    "PostToolUseFailure", "PostToolBatch", "Notification", "MessageDisplay",
    "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted",
    "Stop", "StopFailure", "TeammateIdle", "InstructionsLoaded",
    "ConfigChange", "CwdChanged", "FileChanged", "WorktreeCreate",
    "WorktreeRemove", "PreCompact", "PostCompact", "Elicitation",
    "ElicitationResult", "SessionEnd",
}

_INTERPRETERS: set[str] = {
    "python", "python3", "bash", "sh", "zsh", "node", "deno", "uv",
    "ruby", "perl", "pwsh", "powershell",
}

# Regex: matches a ${CLAUDE_*} path token that is NOT preceded by a double quote.
# The token extends to the next whitespace or double quote.
_UNQUOTED_VAR_RE = re.compile(
    r'(?<!")(\$\{(?:CLAUDE_PLUGIN_ROOT|CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_DATA)\}[^\s"]*)'
)


# --- Utilities -------------------------------------------------------------------

def quote_path_vars(command: str) -> str:
    """Wrap unquoted ${CLAUDE_*} path tokens in double quotes. Idempotent."""
    return _UNQUOTED_VAR_RE.sub(r'"\1"', command)


def _has_unquoted_path_var(command: str) -> bool:
    return quote_path_vars(command) != command


def _tokenize(command: str) -> list[str]:
    """Split a shell command into tokens. Falls back to str.split on bad syntax."""
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _is_bare_path_command(command: str) -> bool:
    """True if the first non-env token is a script path, not an interpreter."""
    for tok in _tokenize(command):
        # Skip leading ENV=val assignments
        if "=" in tok and not tok.startswith("$") and "/" not in tok.split("=")[0]:
            continue
        return tok not in _INTERPRETERS
    return False


def _confine(anchor: Path, candidate: Path) -> Path | None:
    """Resolve candidate and return it only if it stays within anchor (no ../ escape)."""
    try:
        anchor_r = anchor.resolve()
        resolved = candidate.resolve()
        if resolved.is_relative_to(anchor_r):
            return resolved
    except (OSError, ValueError):
        pass
    return None


def _resolve_script_path(command: str, ctx: CheckContext) -> Path | None:
    """Resolve the script path a command references, if statically resolvable.

    Handles ${CLAUDE_PLUGIN_ROOT} (anchored to plugin dir) and
    ${CLAUDE_PROJECT_DIR} (anchored to project dir). Path traversal
    escapes are rejected via _confine.
    """
    for tok in _tokenize(command):
        if "${CLAUDE_PLUGIN_ROOT}" in tok and ctx.plugin_root is not None:
            rel = tok.replace("${CLAUDE_PLUGIN_ROOT}", "").lstrip("/")
            return _confine(ctx.plugin_root, ctx.plugin_root / rel)
        if "${CLAUDE_PROJECT_DIR}" in tok and ctx.project_dir is not None:
            rel = tok.replace("${CLAUDE_PROJECT_DIR}", "").lstrip("/")
            return _confine(ctx.project_dir, ctx.project_dir / rel)
    return None


# --- Handler iteration -----------------------------------------------------------

def iter_handlers(data: dict):
    """Yield (event_name, handler_dict) for every command-type hook handler."""
    for event, blocks in (data.get("hooks") or {}).items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            for h in (block.get("hooks", []) if isinstance(block, dict) else []):
                if isinstance(h, dict):
                    yield event, h


# --- Per-handler checks ----------------------------------------------------------

def _check_event_known(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    if event not in VALID_EVENTS:
        return Finding(
            file=str(ctx.file_path), event=event, command=handler.get("command"),
            check="unknown_event", fixable=False,
            detail=f"'{event}' is not a recognized hook event — it will never fire",
        )
    return None


def _check_has_command(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    if handler.get("type") == "command" and not isinstance(handler.get("command"), str):
        return Finding(
            file=str(ctx.file_path), event=event, command=None,
            check="no_command", fixable=False,
            detail="Handler has type 'command' but no 'command' string",
        )
    return None


def _check_unquoted_var(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    cmd = handler.get("command")
    if isinstance(cmd, str) and _has_unquoted_path_var(cmd):
        return Finding(
            file=str(ctx.file_path), event=event, command=cmd,
            check="unquoted_var", fixable=True,
            detail="Unquoted ${CLAUDE_*} path — breaks in agent-mode where paths contain spaces",
        )
    return None


def _check_script_missing(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    cmd = handler.get("command")
    if not isinstance(cmd, str):
        return None
    script = _resolve_script_path(cmd, ctx)
    if script is not None and not script.exists():
        return Finding(
            file=str(ctx.file_path), event=event, command=cmd,
            check="script_missing", fixable=False,
            detail=f"Referenced script does not exist: {script}",
        )
    return None


def _check_not_executable(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    cmd = handler.get("command")
    if not isinstance(cmd, str):
        return None
    script = _resolve_script_path(cmd, ctx)
    if script is not None and script.exists():
        if _is_bare_path_command(cmd) and not os.access(script, os.X_OK):
            return Finding(
                file=str(ctx.file_path), event=event, command=cmd,
                check="not_executable", fixable=True,
                detail=f"Script is not executable (needs chmod +x): {script}",
            )
    return None


def _check_deprecated_syntax(event: str, handler: dict, ctx: CheckContext) -> Finding | None:
    """Flag handlers using single 'command' string when 'commands' array is available."""
    if handler.get("type") == "command" and "command" in handler and "commands" not in handler:
        return Finding(
            file=str(ctx.file_path), event=event, command=handler.get("command"),
            check="deprecated_syntax", fixable=False,
            detail="Handler uses single 'command' string — consider 'commands' array for multi-command handlers",
        )
    return None


HANDLER_CHECKS: list = [
    _check_event_known,
    _check_has_command,
    _check_unquoted_var,
    _check_script_missing,
    _check_not_executable,
    _check_deprecated_syntax,
]


# --- File-level entry point ------------------------------------------------------

def scan_file(file_path: Path, project_dir: Path | None = None) -> list[Finding]:
    """Parse a hooks/settings file and run all checks. Returns list of Findings."""
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    # File-level: JSON validity (runs before handler iteration)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [Finding(
            file=str(file_path), event=None, command=None,
            check="invalid_json", detail=f"Not valid JSON: {e}", fixable=False,
        )]

    # Determine plugin root for path resolution
    is_plugin = (file_path.name == "hooks.json"
                 and file_path.parent.name == "hooks")
    plugin_root = file_path.parent.parent if is_plugin else None
    ctx = CheckContext(
        file_path=file_path,
        plugin_root=plugin_root,
        project_dir=project_dir,
    )

    findings: list[Finding] = []
    for event, handler in iter_handlers(data):
        for check_fn in HANDLER_CHECKS:
            result = check_fn(event, handler, ctx)
            if result is not None:
                findings.append(result)

    return findings
