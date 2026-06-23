#!/usr/bin/env python3
"""Tests for efficiency-audit."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import scanner


def _make_transcript(messages: list[dict], project_name: str = "test-project") -> Path:
    """Create a temp JSONL transcript file in the structure find_transcript_files expects.

    Claude Code stores transcripts under ~/.claude/projects/<project>/<session>.jsonl.
    """
    tmp_root = Path(tempfile.mkdtemp())
    proj_dir = tmp_root / ".claude" / "projects" / project_name
    proj_dir.mkdir(parents=True)
    path = proj_dir / "session-001.jsonl"
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    # Set mtime to now so it passes the --days filter
    now = datetime.now(tz=timezone.utc).timestamp()
    os.utime(path, (now, now))
    return path


def _home_root(path: Path) -> str:
    """Given a transcript path created by _make_transcript, return the tmp
    root that should be set as HOME so find_transcript_files can discover it."""
    # path = tmp_root/.claude/projects/<project>/session-001.jsonl
    return str(path.parent.parent.parent.parent)


class ParseSessionTests(unittest.TestCase):
    def test_extracts_user_messages(self):
        path = _make_transcript([
            {"type": "user", "message": {"content": "hello world"}, "timestamp": "2026-01-01T00:00:00Z"},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.user_messages), 1)
        self.assertEqual(session.user_messages[0].text, "hello world")

    def test_captures_preceding_action(self):
        path = _make_transcript([
            {"type": "assistant", "message": {"content": "I'll fix that bug now"}, "timestamp": "2026-01-01T00:00:00Z"},
            {"type": "user", "message": {"content": "no, don't commit yet"}, "timestamp": "2026-01-01T00:00:01Z"},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.user_messages), 1)
        self.assertIn("fix that bug", session.user_messages[0].preceding_action)

    def test_extracts_tool_failures(self):
        path = _make_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "tu1", "name": "Write"}
            ]}, "timestamp": "2026-01-01T00:00:00Z"},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu1", "is_error": True,
                 "content": [{"type": "text", "text": "File has not been read yet"}]}
            ]}, "timestamp": "2026-01-01T00:00:01Z"},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.tool_failures), 1)
        self.assertEqual(session.tool_failures[0].tool, "Write")
        self.assertEqual(session.tool_failures[0].error_category, "unread_write")

    def test_extracts_hook_errors_from_system(self):
        path = _make_transcript([
            {"type": "system", "hookErrors": [
                {"hookName": "SessionStart", "exitCode": 127, "stderr": "command not found", "command": "bad-script.sh"}
            ]},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.hook_errors), 1)
        self.assertEqual(session.hook_errors[0].exit_code, 127)

    def test_extracts_hook_errors_from_attachment(self):
        path = _make_transcript([
            {"type": "attachment", "attachment": {
                "type": "hook_non_blocking_error",
                "hookName": "PreToolUse",
                "exitCode": 1,
                "stderr": "failed",
                "command": "check.sh"
            }},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.hook_errors), 1)
        self.assertEqual(session.hook_errors[0].hook_name, "PreToolUse")

    def test_filters_noise_messages(self):
        path = _make_transcript([
            {"type": "user", "message": {"content": "this session is being continued from a previous conversation"}, "timestamp": "2026-01-01T00:00:00Z"},
            {"type": "user", "message": {"content": "real user message here"}, "timestamp": "2026-01-01T00:00:01Z"},
        ])
        session = scanner.parse_session(path)
        self.assertEqual(len(session.user_messages), 1)
        self.assertIn("real user message", session.user_messages[0].text)

    def test_missing_file_returns_none(self):
        result = scanner.parse_session(Path("/nonexistent/session.jsonl"))
        self.assertIsNone(result)

    def test_find_files_by_days(self):
        path = _make_transcript([{"type": "user", "message": {"content": "test"}, "timestamp": "2026-01-01T00:00:00Z"}])
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = _home_root(path)
        try:
            files = scanner.find_transcript_files(days=7)
            self.assertGreaterEqual(len(files), 1)
        finally:
            if old_home:
                os.environ["HOME"] = old_home
            else:
                os.environ.pop("HOME", None)

    def test_find_files_by_project(self):
        path = _make_transcript([{"type": "user", "message": {"content": "test"}, "timestamp": "2026-01-01T00:00:00Z"}], project_name="my-repo")
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = _home_root(path)
        try:
            files = scanner.find_transcript_files(days=30, project="my-repo")
            self.assertGreaterEqual(len(files), 1)
            files_other = scanner.find_transcript_files(days=30, project="other-repo")
            self.assertEqual(len(files_other), 0)
        finally:
            if old_home:
                os.environ["HOME"] = old_home
            else:
                os.environ.pop("HOME", None)

    def test_classify_tool_error_categories(self):
        self.assertEqual(scanner.classify_tool_error("Write", "File has not been read yet"), "unread_write")
        self.assertEqual(scanner.classify_tool_error("Bash", "permission denied"), "permission_denied")
        self.assertEqual(scanner.classify_tool_error("Bash", "No such file or directory"), "file_not_found")
        self.assertEqual(scanner.classify_tool_error("Bash", "not a git repository"), "wrong_context")
        self.assertEqual(scanner.classify_tool_error("Bash", "exit code 128"), "git_error")
        self.assertEqual(scanner.classify_tool_error("Bash", "exit code 1"), "bash_nonzero")
        self.assertEqual(scanner.classify_tool_error("Bash", "request interrupted by user"), "user_interrupted")
