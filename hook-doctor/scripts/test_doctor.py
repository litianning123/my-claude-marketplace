#!/usr/bin/env python3
"""Tests for hook-doctor."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import checks
import sources


class DiscoverSourcesTests(unittest.TestCase):
    def test_returns_empty_list_when_no_configs_exist(self):
        """discover_sources on a temp dir with no .claude should return empty."""
        with tempfile.TemporaryDirectory() as td:
            # Isolate from real user configs by pointing HOME at a clean temp dir
            clean_home = Path(td) / "home"
            clean_home.mkdir()
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(clean_home)
            try:
                result = sources.discover_sources(project_dir=Path(td))
                self.assertEqual(result, [])
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

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
            hooks_dir = base / ".claude" / "plugins" / "my-plugin" / "hooks"
            hooks_dir.mkdir(parents=True)
            (hooks_dir / "hooks.json").write_text("{}")
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                self.assertTrue(
                    any("hooks.json" in str(s.path) for s in result),
                    "Should find hooks.json in plugin tree",
                )
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_dedup_by_realpath(self):
        """Symlinked plugin dir should not produce duplicates."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            base_claude_plugins = base / ".claude" / "plugins"
            real_dir = base_claude_plugins / "real-plugin" / "hooks"
            real_dir.mkdir(parents=True)
            (real_dir / "hooks.json").write_text("{}")
            link_dir = base_claude_plugins / "link-plugin"
            link_dir.mkdir(parents=True)
            (link_dir / "hooks").symlink_to(real_dir)
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                hooks_count = sum(1 for s in result if "hooks.json" in str(s.path))
                self.assertEqual(hooks_count, 1, "Symlinked duplicates should be deduped")
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]


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
