# Hook Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin that statically analyzes hook configurations for 7 misconfiguration patterns and auto-repairs 2 of them.

**Architecture:** Four independent Python modules — `sources.py` (discovery), `checks.py` (7 checks + data model), `fixer.py` (2 repair functions), `doctor.py` (CLI orchestration). Each module has one responsibility and a clean interface to its neighbors. Stdlib-only.

**Tech Stack:** Python 3.10+, stdlib `unittest`, `argparse`, `pathlib`, `json`, `re`, `dataclasses`. No third-party packages.

## Global Constraints

- Python 3.10+ (for `str | None` union syntax)
- Stdlib only — no pip install, no requirements.txt
- No build system — scripts run directly with `python3`
- SKILL.md must be concise and structured (4 phases max)
- All checks are static — no hook execution
- Validate-before-write for all JSON mutations
- Symlink refusal for all `chmod` operations
- Path confinement — `../` escapes rejected

---

### Task 1: Scaffold — Directory Structure & Plugin Manifest

**Files:**
- Create: `hook-doctor/.claude-plugin/plugin.json`
- Create: `hook-doctor/skills/hook-doctor/SKILL.md` (placeholder)
- Create: `hook-doctor/scripts/__init__.py` (empty)
- Create: `hook-doctor/README.md` (placeholder)

**Interfaces:**
- Consumes: nothing
- Produces: directory layout, `plugin.json` with `{"name": "hook-doctor", "description": "..."}`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p hook-doctor/.claude-plugin
mkdir -p hook-doctor/skills/hook-doctor
mkdir -p hook-doctor/scripts
```

- [ ] **Step 2: Write plugin.json**

```json
{
  "name": "hook-doctor",
  "description": "Inspects and repairs Claude Code hook configurations. Detects unquoted path variables, missing scripts, non-executable scripts, unknown events, invalid JSON, missing command fields, and deprecated handler syntax — then applies safe, idempotent fixes with explicit approval."
}
```

Write to `hook-doctor/.claude-plugin/plugin.json`.

- [ ] **Step 3: Create empty __init__.py and placeholder SKILL.md**

```bash
touch hook-doctor/scripts/__init__.py
```

Write `hook-doctor/skills/hook-doctor/SKILL.md` as a one-line placeholder:
```
# hook-doctor (implementation pending)
```

- [ ] **Step 4: Create placeholder README.md**

Write `hook-doctor/README.md` as a one-line placeholder:
```
# hook-doctor (implementation pending)
```

- [ ] **Step 5: Verify structure**

```bash
find hook-doctor -type f | sort
```

Expected output:
```
hook-doctor/.claude-plugin/plugin.json
hook-doctor/README.md
hook-doctor/scripts/__init__.py
hook-doctor/skills/hook-doctor/SKILL.md
```

- [ ] **Step 6: Commit**

```bash
git add hook-doctor/
git commit -m "scaffold: create hook-doctor directory structure and plugin manifest"
```

---

### Task 2: Source Discovery (`sources.py`)

**Files:**
- Create: `hook-doctor/scripts/sources.py`
- Modify: `hook-doctor/scripts/test_doctor.py` (create with first tests)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `HookSource(path: Path, project_dir: Path | None)` — dataclass
  - `discover_sources(project_dir: Path | None = None) -> list[HookSource]`
  - `find_plugin_hooks(root: Path) -> list[Path]` — walks tree for hooks.json, deduped by realpath

- [ ] **Step 1: Write the failing test**

Create `hook-doctor/scripts/test_doctor.py`:

```python
#!/usr/bin/env python3
"""Tests for hook-doctor."""
import tempfile
import unittest
from pathlib import Path

import sources


class DiscoverSourcesTests(unittest.TestCase):
    def test_returns_empty_list_when_no_configs_exist(self):
        """discover_sources on a temp dir with no .claude should return empty."""
        with tempfile.TemporaryDirectory() as td:
            result = sources.discover_sources(project_dir=Path(td))
            self.assertEqual(result, [])

    def test_finds_project_settings_json(self):
        """A project with .claude/settings.json should be discovered."""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            (proj / ".claude").mkdir()
            (proj / ".claude" / "settings.json").write_text("{}")
            result = sources.discover_sources(project_dir=proj)
            paths = [str(s.path) for s in result]
            self.assertIn(str((proj / ".claude" / "settings.json").resolve()), paths)

    def test_finds_plugin_hooks_json(self):
        """hooks.json under a plugins dir should be discovered."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            hooks_dir = base / "plugins" / "my-plugin" / "hooks"
            hooks_dir.mkdir(parents=True)
            (hooks_dir / "hooks.json").write_text("{}")
            # Patch home to point at our temp dir
            import os
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                self.assertTrue(
                    any("hooks.json" in str(s.path) for s in result),
                    "Should find hooks.json in plugin tree",
                )
            finally:
                if old_home:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_dedup_by_realpath(self):
        """Symlinked plugin dir should not produce duplicates."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            real_dir = base / "plugins" / "real-plugin" / "hooks"
            real_dir.mkdir(parents=True)
            (real_dir / "hooks.json").write_text("{}")
            link_dir = base / "plugins" / "link-plugin"
            link_dir.mkdir(parents=True)
            (link_dir / "hooks").symlink_to(real_dir)
            import os
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                hooks_count = sum(1 for s in result if "hooks.json" in str(s.path))
                self.assertEqual(hooks_count, 1, "Symlinked duplicates should be deduped")
            finally:
                if old_home:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor.DiscoverSourcesTests -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 3: Write sources.py implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor.DiscoverSourcesTests -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add hook-doctor/scripts/sources.py hook-doctor/scripts/test_doctor.py
git commit -m "feat: add hook source discovery module

Discovers hooks.json and settings.json from three locations:
user-level, project-level, and installed plugins. Deduplicates
by realpath and handles missing directories gracefully."
```

---

### Task 3: Check Engine (`checks.py`)

**Files:**
- Create: `hook-doctor/scripts/checks.py`
- Modify: `hook-doctor/scripts/test_doctor.py` (add check tests)

**Interfaces:**
- Consumes: nothing (self-contained data model)
- Produces:
  - `Finding(file, event, command, check, detail, fixable)` — dataclass
  - `CheckContext(file_path, plugin_root, project_dir)` — dataclass
  - `scan_file(file_path: Path, project_dir: Path | None = None) -> list[Finding]`
  - `iter_handlers(data: dict)` — yields `(event_name, handler_dict)` tuples
  - `quote_path_vars(command: str) -> str` — utility for check #4
  - `ALL_CHECKS: list` — registry of handler-level checks
  - `VALID_EVENTS: set[str]` — recognized Claude Code hook event names

- [ ] **Step 1: Append failing tests to test_doctor.py**

Add to `test_doctor.py`:

```python
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import checks


def _make_plugin_hooks(events: dict, scripts: dict | None = None,
                       raw: str | None = None) -> Path:
    """Create a temp plugin dir with hooks/hooks.json. Returns path to hooks.json.

    events: {event_name: command_string}
    scripts: {relative_path: (content, executable_bool)}
    raw: override hooks.json content verbatim
    """
    plugin = Path(tempfile.mkdtemp()) / "plugin"
    (plugin / "hooks").mkdir(parents=True)
    path = plugin / "hooks" / "hooks.json"
    if raw is not None:
        path.write_text(raw)
    else:
        d = {"hooks": {ev: [{"hooks": [{"type": "command", "command": cmd}]}]
                       for ev, cmd in events.items()}}
        path.write_text(json.dumps(d, indent=2) + "\n")
    for rel, (content, executable) in (scripts or {}).items():
        sp = plugin / rel
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(content)
        mode = sp.stat().st_mode
        sp.chmod(mode | 0o111 if executable else mode & ~0o111)
    return path


def _slugs(findings: list) -> set:
    return {f.check for f in findings}


class CheckInvalidJsonTests(unittest.TestCase):
    def test_invalid_json_detected(self):
        path = _make_plugin_hooks({}, raw='{"hooks": {bad')
        findings = checks.scan_file(path)
        self.assertIn("invalid_json", _slugs(findings))

    def test_valid_json_clean(self):
        path = _make_plugin_hooks({"SessionStart": "echo hi"})
        findings = checks.scan_file(path)
        self.assertNotIn("invalid_json", _slugs(findings))

    def test_missing_file_no_crash(self):
        findings = checks.scan_file(Path("/nonexistent/hooks.json"))
        self.assertEqual(findings, [])


class CheckUnknownEventTests(unittest.TestCase):
    def test_unknown_event_reported(self):
        path = _make_plugin_hooks({"TotallyFakeEvent": "echo hi"})
        findings = checks.scan_file(path)
        self.assertIn("unknown_event", _slugs(findings))

    def test_valid_event_clean(self):
        for ev in ("SessionStart", "PreToolUse", "PostToolUse", "Stop"):
            path = _make_plugin_hooks({ev: "echo hi"})
            findings = checks.scan_file(path)
            self.assertNotIn("unknown_event", _slugs(findings))


class CheckNoCommandTests(unittest.TestCase):
    def test_missing_command_field_reported(self):
        raw = json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}})
        path = _make_plugin_hooks({}, raw=raw)
        findings = checks.scan_file(path)
        self.assertIn("no_command", _slugs(findings))

    def test_has_command_field_clean(self):
        path = _make_plugin_hooks({"Stop": "echo done"})
        findings = checks.scan_file(path)
        self.assertNotIn("no_command", _slugs(findings))

    def test_non_command_handler_skipped(self):
        raw = json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "prompt"}]}]}})
        path = _make_plugin_hooks({}, raw=raw)
        findings = checks.scan_file(path)
        self.assertNotIn("no_command", _slugs(findings))


class CheckUnquotedVarTests(unittest.TestCase):
    def test_unquoted_plugin_root_detected(self):
        path = _make_plugin_hooks({"SessionStart": "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"})
        findings = checks.scan_file(path)
        self.assertIn("unquoted_var", _slugs(findings))

    def test_unquoted_project_dir_detected(self):
        path = _make_plugin_hooks({"Stop": "bash ${CLAUDE_PROJECT_DIR}/hooks/h.sh"})
        findings = checks.scan_file(path)
        self.assertIn("unquoted_var", _slugs(findings))

    def test_unquoted_plugin_data_detected(self):
        path = _make_plugin_hooks({"SessionStart": "${CLAUDE_PLUGIN_DATA}/state.sh"})
        findings = checks.scan_file(path)
        self.assertIn("unquoted_var", _slugs(findings))

    def test_quoted_var_clean(self):
        path = _make_plugin_hooks(
            {"SessionStart": '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"'})
        findings = checks.scan_file(path)
        self.assertNotIn("unquoted_var", _slugs(findings))

    def test_interpreter_with_unquoted_var_detected(self):
        path = _make_plugin_hooks(
            {"PreToolUse": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/y.py"})
        findings = checks.scan_file(path)
        self.assertIn("unquoted_var", _slugs(findings))

    def test_unquoted_is_fixable(self):
        path = _make_plugin_hooks({"SessionStart": "${CLAUDE_PLUGIN_ROOT}/x.sh"})
        findings = checks.scan_file(path)
        uf = next(f for f in findings if f.check == "unquoted_var")
        self.assertTrue(uf.fixable)


class CheckScriptMissingTests(unittest.TestCase):
    def test_missing_script_reported(self):
        path = _make_plugin_hooks(
            {"SessionStart": '"${CLAUDE_PLUGIN_ROOT}/scripts/gone.sh"'})
        findings = checks.scan_file(path)
        self.assertIn("script_missing", _slugs(findings))

    def test_existing_script_clean(self):
        path = _make_plugin_hooks(
            {"SessionStart": '"${CLAUDE_PLUGIN_ROOT}/scripts/here.sh"'},
            scripts={"scripts/here.sh": ("#!/bin/sh\necho hi\n", True)},
        )
        findings = checks.scan_file(path)
        self.assertNotIn("script_missing", _slugs(findings))

    def test_traversal_ignored(self):
        """../ escape outside plugin root must not be resolved or reported."""
        path = _make_plugin_hooks(
            {"Stop": '"${CLAUDE_PLUGIN_ROOT}/../escape.sh"'})
        findings = checks.scan_file(path)
        self.assertNotIn("script_missing", _slugs(findings))


class CheckNotExecutableTests(unittest.TestCase):
    def test_bare_path_not_executable_reported(self):
        path = _make_plugin_hooks(
            {"Stop": '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"'},
            scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", False)},
        )
        findings = checks.scan_file(path)
        self.assertIn("not_executable", _slugs(findings))

    def test_interpreter_prefixed_ok(self):
        """python3 script.py doesn't need the execute bit."""
        path = _make_plugin_hooks(
            {"Stop": 'python3 "${CLAUDE_PLUGIN_ROOT}/x.py"'},
            scripts={"x.py": ("print(1)\n", False)},
        )
        findings = checks.scan_file(path)
        self.assertNotIn("not_executable", _slugs(findings))

    def test_executable_script_clean(self):
        path = _make_plugin_hooks(
            {"Stop": '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"'},
            scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", True)},
        )
        findings = checks.scan_file(path)
        self.assertNotIn("not_executable", _slugs(findings))


class CheckDeprecatedSyntaxTests(unittest.TestCase):
    def test_single_command_detected(self):
        path = _make_plugin_hooks({"SessionStart": "echo hi"})
        findings = checks.scan_file(path)
        self.assertIn("deprecated_syntax", _slugs(findings))
        df = next(f for f in findings if f.check == "deprecated_syntax")
        self.assertFalse(df.fixable)

    def test_commands_array_clean(self):
        raw = json.dumps({
            "hooks": {
                "SessionStart": [{"hooks": [{
                    "type": "command",
                    "commands": ["echo one", "echo two"]
                }]}]
            }
        })
        path = _make_plugin_hooks({}, raw=raw)
        findings = checks.scan_file(path)
        self.assertNotIn("deprecated_syntax", _slugs(findings))


class QuotePathVarsTests(unittest.TestCase):
    def test_wraps_bare_var(self):
        self.assertEqual(
            checks.quote_path_vars("${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"),
            '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"',
        )

    def test_handles_interpreter_prefix(self):
        self.assertEqual(
            checks.quote_path_vars("python3 ${CLAUDE_PLUGIN_ROOT}/x.py"),
            'python3 "${CLAUDE_PLUGIN_ROOT}/x.py"',
        )

    def test_already_quoted_is_idempotent(self):
        once = checks.quote_path_vars('"${CLAUDE_PLUGIN_ROOT}/x.sh"')
        self.assertEqual(checks.quote_path_vars(once), once)

    def test_no_path_var_unchanged(self):
        self.assertEqual(checks.quote_path_vars("echo hello"), "echo hello")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor -v 2>&1 | head -5
```

Expected: FAIL with `ModuleNotFoundError: No module named 'checks'`

- [ ] **Step 3: Write checks.py implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify all check tests pass**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor -v
```

Expected: all tests in Check* and QuotePathVars classes PASS

- [ ] **Step 5: Commit**

```bash
git add hook-doctor/scripts/checks.py hook-doctor/scripts/test_doctor.py
git commit -m "feat: add check engine with 7 static hook config checks

Check protocol with per-handler functions, Finding data model,
and CheckContext for path resolution. Checks: invalid_json,
unknown_event, no_command, unquoted_var, script_missing,
not_executable, deprecated_syntax. Path confinement prevents
../ traversal."
```

---

### Task 4: Fixer (`fixer.py`)

**Files:**
- Create: `hook-doctor/scripts/fixer.py`
- Modify: `hook-doctor/scripts/test_doctor.py` (add fixer tests)

**Interfaces:**
- Consumes: `checks.Finding` (for `fix_executable`), `checks.quote_path_vars`
- Produces:
  - `fix_unquoted_vars(file_path: Path) -> int` — count of commands fixed
  - `fix_executable(finding: Finding) -> bool` — success/failure

- [ ] **Step 1: Append failing fixer tests to test_doctor.py**

Add to `test_doctor.py`:

```python
import fixer


class FixUnquotedVarsTests(unittest.TestCase):
    def test_fix_wraps_unquoted_var(self):
        path = _make_plugin_hooks({
            "SessionStart": "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh",
        }, scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", True)})
        self.assertEqual(fixer.fix_unquoted_vars(path), 1)
        data = json.loads(path.read_text())
        cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertIn('"', cmd)
        # Re-scan should be clean
        self.assertNotIn("unquoted_var", _slugs(checks.scan_file(path)))

    def test_fix_handles_multiple_commands(self):
        path = _make_plugin_hooks({
            "SessionStart": "${CLAUDE_PLUGIN_ROOT}/a.sh",
            "PreToolUse": "python3 ${CLAUDE_PLUGIN_ROOT}/b.py",
        }, scripts={
            "a.sh": ("#!/bin/sh\necho a\n", True),
            "b.py": ("print(1)\n", False),
        })
        self.assertEqual(fixer.fix_unquoted_vars(path), 2)
        data = json.loads(path.read_text())
        for ev in ("SessionStart", "PreToolUse"):
            cmd = data["hooks"][ev][0]["hooks"][0]["command"]
            self.assertIn('"', cmd)

    def test_fix_idempotent(self):
        path = _make_plugin_hooks({
            "SessionStart": "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh",
        }, scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", True)})
        self.assertEqual(fixer.fix_unquoted_vars(path), 1)
        self.assertEqual(fixer.fix_unquoted_vars(path), 0)

    def test_fix_preserves_unrelated_commands(self):
        path = _make_plugin_hooks({
            "SessionStart": "${CLAUDE_PLUGIN_ROOT}/x.sh",
            "Stop": "echo done",
        }, scripts={"x.sh": ("#!/bin/sh\necho hi\n", True)})
        fixer.fix_unquoted_vars(path)
        data = json.loads(path.read_text())
        stop_cmd = data["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertEqual(stop_cmd, "echo done")

    def test_fix_invalid_json_returns_zero(self):
        path = _make_plugin_hooks({}, raw="not json at all")
        self.assertEqual(fixer.fix_unquoted_vars(path), 0)

    def test_fix_already_quoted_returns_zero(self):
        path = _make_plugin_hooks({
            "SessionStart": '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"',
        }, scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", True)})
        self.assertEqual(fixer.fix_unquoted_vars(path), 0)

    def test_output_is_valid_json_after_fix(self):
        path = _make_plugin_hooks({
            "SessionStart": "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh",
        }, scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", True)})
        fixer.fix_unquoted_vars(path)
        json.loads(path.read_text())  # must not raise


class FixExecutableTests(unittest.TestCase):
    def test_chmod_makes_executable(self):
        path = _make_plugin_hooks(
            {"Stop": '"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"'},
            scripts={"scripts/x.sh": ("#!/bin/sh\necho hi\n", False)},
        )
        findings = checks.scan_file(path)
        ne = next(f for f in findings if f.check == "not_executable")
        self.assertTrue(fixer.fix_executable(ne))
        self.assertTrue(os.access(ne.detail.split(": ")[-1], os.X_OK))

    def test_refuses_symlink(self):
        tmp = Path(tempfile.mkdtemp())
        real = tmp / "real.sh"
        real.write_text("#!/bin/sh\necho hi\n")
        real.chmod(real.stat().st_mode & ~0o111)
        link = tmp / "link.sh"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        from checks import Finding
        f = Finding(file="", event="Stop", command="cmd",
                    check="not_executable", detail=f"needs chmod +x: {link}",
                    fixable=True)
        self.assertFalse(fixer.fix_executable(f))
        self.assertFalse(os.access(real, os.X_OK))

    def test_missing_target_file_returns_false(self):
        from checks import Finding
        f = Finding(file="", event="Stop", command="cmd",
                    check="not_executable",
                    detail="Script is not executable (needs chmod +x): /nonexistent/x.sh",
                    fixable=True)
        self.assertFalse(fixer.fix_executable(f))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor.FixUnquotedVarsTests -v 2>&1 | head -3
```

Expected: FAIL with `ModuleNotFoundError: No module named 'fixer'`

- [ ] **Step 3: Write fixer.py implementation**

```python
#!/usr/bin/env python3
"""Fix application — safe, idempotent repairs for hook config problems."""

import json
import os
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

    # Collect old→new replacements
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
    # Extract path from detail string: "... (needs chmod +x: /path/to/script)"
    detail = finding.detail
    marker = "needs chmod +x: "
    idx = detail.rfind(marker)
    if idx == -1:
        return False

    script_path = detail[idx + len(marker):].strip()
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
```

- [ ] **Step 4: Run all tests**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor -v
```

Expected: all tests pass, including FixUnquotedVarsTests and FixExecutableTests

- [ ] **Step 5: Commit**

```bash
git add hook-doctor/scripts/fixer.py hook-doctor/scripts/test_doctor.py
git commit -m "feat: add fixer module with safe, idempotent repairs

Two fix functions: fix_unquoted_vars (surgical JSON quoting,
validates before write) and fix_executable (chmod +x with
symlink TOCTOU guard). Both are idempotent — running twice
on an already-fixed file is a no-op."
```

---

### Task 5: CLI Orchestration (`doctor.py`)

**Files:**
- Create: `hook-doctor/scripts/doctor.py`
- Modify: `hook-doctor/scripts/test_doctor.py` (add integration tests)

**Interfaces:**
- Consumes: `sources.discover_sources`, `checks.scan_file`, `fixer.fix_unquoted_vars`, `fixer.fix_executable`
- Produces: CLI with `--project`, `--root`, `--apply` flags

- [ ] **Step 1: Append failing integration tests to test_doctor.py**

Add to `test_doctor.py`:

```python
import subprocess
import sys


class IntegrationTests(unittest.TestCase):
    def test_report_mode_detects_problems(self):
        """Running doctor.py on a temp plugin with known issues prints findings."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin = base / "plugins" / "bad-plugin" / "hooks"
            plugin.mkdir(parents=True)
            hooks = plugin / "hooks.json"
            d = {
                "hooks": {
                    "SessionStart": [{"hooks": [{
                        "type": "command",
                        "command": "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh"
                    }]}]
                }
            }
            hooks.write_text(json.dumps(d, indent=2))

            import os
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = subprocess.run(
                    [sys.executable, "doctor.py", "--root", str(base / "plugins")],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent),
                )
                self.assertIn("unquoted_var", result.stdout)
                self.assertIn("script_missing", result.stdout)
                self.assertIn("fixable", result.stdout.lower()
                               or "unquoted_var" in result.stdout)
            finally:
                if old_home:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_apply_mode_fixes_problems(self):
        """Running with --apply should fix unquoted vars."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin = base / "plugins" / "bad-plugin" / "hooks"
            plugin.mkdir(parents=True)
            scripts_dir = base / "plugins" / "bad-plugin" / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "run.sh").write_text("#!/bin/sh\necho hi\n")
            (scripts_dir / "run.sh").chmod(0o755)

            hooks = plugin / "hooks.json"
            d = {
                "hooks": {
                    "SessionStart": [{"hooks": [{
                        "type": "command",
                        "command": "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh"
                    }]}]
                }
            }
            hooks.write_text(json.dumps(d, indent=2))

            import os
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = subprocess.run(
                    [sys.executable, "doctor.py", "--root",
                     str(base / "plugins"), "--apply"],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent),
                )
                # After fix, re-read the file
                data = json.loads(hooks.read_text())
                cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
                self.assertIn('"', cmd)
            finally:
                if old_home:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_clean_config_reports_no_problems(self):
        """A valid config should produce no findings."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plugin = base / "plugins" / "good-plugin" / "hooks"
            plugin.mkdir(parents=True)
            hooks = plugin / "hooks.json"
            d = {
                "hooks": {
                    "SessionStart": [{"hooks": [{
                        "type": "command",
                        "command": "echo ready"
                    }]}]
                }
            }
            hooks.write_text(json.dumps(d, indent=2))

            import os
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = subprocess.run(
                    [sys.executable, "doctor.py", "--root", str(base / "plugins")],
                    capture_output=True, text=True, cwd=str(Path(__file__).parent),
                )
                self.assertIn("No hook configuration problems found",
                              result.stdout)
            finally:
                if old_home:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor.IntegrationTests -v 2>&1 | head -5
```

Expected: FAIL — `doctor.py` doesn't exist yet or exits with error

- [ ] **Step 3: Write doctor.py implementation**

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor -v
```

Expected: all tests pass, including IntegrationTests

- [ ] **Step 5: Commit**

```bash
git add hook-doctor/scripts/doctor.py hook-doctor/scripts/test_doctor.py
git commit -m "feat: add CLI orchestration layer

Thin argparse wrapper over sources → checks → fixer pipeline.
Three flags: --project, --root, --apply. Reports findings
grouped by file. With --apply, fixes unquoted vars and
non-executable scripts, then re-scans to verify."
```

---

### Task 6: Agent Procedure (`SKILL.md`) & README

**Files:**
- Modify: `hook-doctor/skills/hook-doctor/SKILL.md` (replace placeholder)
- Modify: `hook-doctor/README.md` (replace placeholder)

**Interfaces:**
- Consumes: final plugin behavior from all modules
- Produces: skill description with trigger phrases, 4-phase procedure, human-facing README

- [ ] **Step 1: Write SKILL.md**

Replace `hook-doctor/skills/hook-doctor/SKILL.md`:

```markdown
---
name: hook-doctor
description: "Inspects and repairs Claude Code hook configurations — plugin hooks.json and project/user settings.json. Use when a hook is failing or misconfigured, when an efficiency audit reports hook_errors, or when the user asks to check, diagnose, or fix hooks. Detects unquoted ${CLAUDE_PLUGIN_ROOT}/${CLAUDE_PROJECT_DIR} commands that fail in agent-mode (exit 127, '/bin/sh: .../Library/Application: No such file'), missing/non-executable scripts, unknown events, invalid JSON, missing command fields, and deprecated single-command syntax. Trigger phrases: 'fix my hooks', 'hook is broken', 'why did my hook fail', 'check my plugin hooks', 'diagnose hook errors', 'hook exit 127'."
---

# Hook Doctor

Diagnose and repair Claude Code hook configurations. Static analysis only — no hooks are executed.

## 0. Intent

Ask before scanning:
> "Diagnose-only, or apply fixes if found? All hooks or a specific plugin?"

## 1. Scan

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/hook-doctor/*/ 2>/dev/null | head -1)
python3 "${PLUGIN_ROOT}/scripts/doctor.py" [--project DIR] [--root DIR]
```

Group findings by file. Flag fixable vs. report-only clearly.

## 2. Decide

For each fixable finding, state the blast radius (installed plugin file vs. user settings) and offer:
- **(a)** fix locally
- **(b)** upstream PR
- **(c)** both
- **(d)** skip

Never edit without explicit choice. Show the exact change before applying.

## 3. Apply & Verify

```bash
python3 "${PLUGIN_ROOT}/scripts/doctor.py" --apply [same flags as scan]
```

Re-scan to confirm findings are resolved. If the fixed file is in a git repo, show `git diff`.

## Checks Reference

| Check | Problem | Fixable? |
|-------|---------|----------|
| `invalid_json` | File doesn't parse as JSON | No |
| `unknown_event` | Event name not recognized | No |
| `no_command` | Command handler missing command string | No |
| `unquoted_var` | `${CLAUDE_*}` path unquoted (breaks agent-mode) | **Yes** |
| `script_missing` | Referenced script doesn't exist | No |
| `not_executable` | Bare-path script lacks execute bit | **Yes** |
| `deprecated_syntax` | Single `command` instead of `commands` array | No |
```

- [ ] **Step 2: Write README.md**

Replace `hook-doctor/README.md`:

```markdown
# hook-doctor

Inspects and repairs **Claude Code plugin hook configurations** — the `hooks/hooks.json`
files under `~/.claude/plugins/` and user/project `settings.json`. Scans every installed
plugin for known hook-config problems, reports them, and (with explicit opt-in) applies
safe, idempotent fixes.

> **Canonical behavior lives in [`SKILL.md`](skills/hook-doctor/SKILL.md).** This README covers
> human-facing install, direct CLI usage, and testing. If the two disagree, `SKILL.md` wins.

## What it checks

All checks are **static** (no hooks are run). 7 checks total, 2 auto-fixable.

| Check | Problem | Fix |
|-------|---------|-----|
| `unquoted_var` | `${CLAUDE_PLUGIN_ROOT}` unquoted — breaks in agent-mode where paths contain spaces | Fixable — wrap the token in double quotes |
| `not_executable` | Bare-path script lacks execute bit | Fixable — `chmod +x` (with symlink guard) |
| `script_missing` | Referenced script doesn't exist on disk | Report-only |
| `unknown_event` | Event name not recognized — hook never fires | Report-only |
| `no_command` | `type: "command"` handler has no `command` string | Report-only |
| `invalid_json` | File doesn't parse as JSON | Report-only |
| `deprecated_syntax` | Single `command` string where `commands` array is available | Report-only |

## Install

```
/plugin marketplace add <your-marketplace>
/plugin install hook-doctor@<your-marketplace>
```

## Running directly

```bash
# Inspect effective hooks for the current project
python3 scripts/doctor.py

# Inspect a specific project
python3 scripts/doctor.py --project /path/to/repo

# Scan only a plugin tree
python3 scripts/doctor.py --root ~/.claude/plugins/marketplaces/some-marketplace

# Apply fixes
python3 scripts/doctor.py --apply
```

| Flag | Meaning |
|------|---------|
| `--project DIR` | Project to inspect (default: cwd) |
| `--root DIR` | Scan only this tree (skips settings.json) |
| `--apply` | Write fixes (without it, report only) |

## Tests

Standard-library `unittest`, no dependencies:

```bash
cd scripts && python3 -m unittest test_doctor -v
```

## Files

```
hook-doctor/
├── .claude-plugin/plugin.json       # Plugin manifest
├── skills/hook-doctor/SKILL.md      # Agent procedure (4-phase)
├── README.md                        # This file
└── scripts/
    ├── doctor.py                    # CLI entrypoint + orchestration
    ├── sources.py                   # Hook source discovery
    ├── checks.py                    # Check protocol, registry, 7 checks
    ├── fixer.py                     # Fix application
    └── test_doctor.py               # Test suite (unittest)
```
```

- [ ] **Step 3: Verify SKILL.md frontmatter**

```bash
python3 -c "
import yaml_loader_available_or_not
# Manual check: read the file and verify --- ... --- frontmatter is valid
with open('hook-doctor/skills/hook-doctor/SKILL.md') as f:
    content = f.read()
    assert content.startswith('---'), 'Missing frontmatter'
    parts = content.split('---', 2)
    assert len(parts) >= 3, 'Malformed frontmatter'
    print('SKILL.md frontmatter looks valid')
"
```

- [ ] **Step 4: Commit**

```bash
git add hook-doctor/skills/hook-doctor/SKILL.md hook-doctor/README.md
git commit -m "docs: add SKILL.md agent procedure and README

4-phase SKILL.md: Intent → Scan → Decide → Apply & Verify.
Concise trigger phrases in frontmatter description.
Human-facing README with install, usage, and test instructions."
```

---

### Task 7: Final Verification

**Files:** none modified — verification only

- [ ] **Step 1: Run full test suite**

```bash
cd hook-doctor/scripts && python3 -m unittest test_doctor -v
```

Expected: ALL tests pass, zero failures, zero errors.

- [ ] **Step 2: Verify Python version compatibility**

```bash
python3 -c "import sys; assert sys.version_info >= (3, 10), f'Need 3.10+, got {sys.version_info}'; print(f'Python {sys.version} OK')"
```

- [ ] **Step 3: Verify no third-party imports**

```bash
python3 -c "
import ast, sys
files = ['hook-doctor/scripts/sources.py', 'hook-doctor/scripts/checks.py',
         'hook-doctor/scripts/fixer.py', 'hook-doctor/scripts/doctor.py']
stdlib = {'argparse', 'json', 'os', 're', 'shlex', 'sys', 'pathlib', 'dataclasses',
          'tempfile', 'unittest', 'subprocess', 'stat'}
for f in files:
    tree = ast.parse(open(f).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split('.')[0]
                assert mod in stdlib, f'{f} imports non-stdlib: {mod}'
        elif isinstance(node, ast.ImportFrom):
            mod = node.module.split('.')[0] if node.module else ''
            assert mod in stdlib or node.module in ('__future__',),
                f'{f} imports non-stdlib: {node.module}'
print('All imports are stdlib ✓')
"
```

- [ ] **Step 4: Verify file structure**

```bash
find hook-doctor -type f | sort
```

Expected:
```
hook-doctor/.claude-plugin/plugin.json
hook-doctor/README.md
hook-doctor/scripts/__init__.py
hook-doctor/scripts/checks.py
hook-doctor/scripts/doctor.py
hook-doctor/scripts/fixer.py
hook-doctor/scripts/sources.py
hook-doctor/scripts/test_doctor.py
hook-doctor/skills/hook-doctor/SKILL.md
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git diff --cached --stat
git commit -m "chore: final verification — all tests pass, stdlib only"
```
