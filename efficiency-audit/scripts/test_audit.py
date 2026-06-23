#!/usr/bin/env python3
"""Tests for efficiency-audit."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import scanner
import patterns


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


class ScoreMessageTests(unittest.TestCase):
    def test_detects_correction(self):
        result = patterns.score_message("no, don't commit yet")
        self.assertGreater(len(result["corrections"]), 0)

    def test_detects_context_request(self):
        result = patterns.score_message("as I said before, we use postgres")
        self.assertGreater(len(result["context_requests"]), 0)

    def test_detects_slow_start(self):
        result = patterns.score_message("first, let's check the project uses python 3.10")
        self.assertGreater(len(result["slow_start"]), 0)

    def test_detects_automation(self):
        result = patterns.score_message("every time I push, I have to run the linter")
        self.assertGreater(len(result["automation"]), 0)

    def test_detects_git_workflow(self):
        result = patterns.score_message("the PR shows 47 files changed, that's wrong")
        self.assertGreater(len(result["git_workflow"]), 0)

    def test_clean_message_returns_empty(self):
        result = patterns.score_message("looks good, thanks")
        self.assertEqual(sum(len(v) for v in result.values()), 0)

    def test_noise_is_filtered(self):
        self.assertTrue(patterns._is_noise("this session is being continued from a previous conversation"))
        self.assertTrue(patterns._is_noise("Base directory for this skill"))
        self.assertFalse(patterns._is_noise("please fix the bug in the login handler"))


class GroupByPatternTests(unittest.TestCase):
    def test_first_pattern_wins(self):
        items = [
            {"text": "no, don't do that, as I said before", "session": "s1",
             "project": "test", "patterns": ["p1_correction", "p2_context"],
             "preceding_action": "did something"},
        ]
        groups = patterns.group_by_pattern(items, "corrections")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 1)

    def test_groups_by_pattern(self):
        items = [
            {"text": "msg A", "session": "s1", "project": "test",
             "patterns": ["p1"], "preceding_action": None},
            {"text": "msg B", "session": "s1", "project": "test",
             "patterns": ["p1"], "preceding_action": None},
            {"text": "msg C", "session": "s2", "project": "test",
             "patterns": ["p2"], "preceding_action": None},
        ]
        groups = patterns.group_by_pattern(items, "corrections")
        self.assertEqual(len(groups), 2)
        p1_group = next(g for g in groups if g.pattern == "p1")
        self.assertEqual(p1_group.count, 2)
        self.assertEqual(p1_group.sessions, 1)


class AnalyzeIntegrationTests(unittest.TestCase):
    def test_empty_sessions_produces_empty_findings(self):
        result = patterns.analyze([])
        self.assertEqual(result["summary"]["sessions_analyzed"], 0)
        for cat in ["corrections", "missing_context", "slow_start_context",
                     "automation_candidates", "git_workflow_errors"]:
            self.assertEqual(result[cat], [])

    def test_sessions_with_messages_produce_findings(self):
        from scanner import SessionData, UserMessage
        sessions = [
            SessionData(
                path="/tmp/test.jsonl", project="test", session_id="s1",
                user_messages=[
                    UserMessage(text="no, don't commit yet", timestamp="2026-01-01T00:00:00Z", preceding_action="committed abc123"),
                ],
            ),
        ]
        result = patterns.analyze(sessions)
        self.assertGreater(len(result["corrections"]), 0)


import synthesizer


class SynthesizerTests(unittest.TestCase):
    def test_generates_correction_recommendation(self):
        findings = {
            "summary": {"sessions_analyzed": 5, "total_user_messages": 100},
            "corrections": [{
                "pattern": r"\bno[,!]?\s+(don'?t)",
                "category": "corrections",
                "count": 5,
                "sessions": 3,
                "top_project": "my-repo",
                "examples": ["no, don't commit yet"],
                "preceding_action": "committed abc123",
            }],
            "missing_context": [],
            "slow_start_context": [],
            "automation_candidates": [],
            "git_workflow_errors": [],
            "hook_errors": [],
            "tool_failures": [],
        }
        recs = synthesizer.generate(findings)
        self.assertGreater(len(recs), 0)
        rec = recs[0]
        self.assertEqual(rec.category, "corrections")
        self.assertIn("commit", rec.proposed_rule.lower())
        self.assertEqual(rec.estimated_tokens_saved, 500)  # 5 × 100
        self.assertEqual(rec.confidence, "high")
        self.assertEqual(rec.target, "CLAUDE.md")

    def test_filters_below_threshold(self):
        findings = {
            "summary": {"sessions_analyzed": 5, "total_user_messages": 100},
            "corrections": [{
                "pattern": "pat", "category": "corrections",
                "count": 1, "sessions": 1, "top_project": "test",
                "examples": ["no"], "preceding_action": None,
            }],
            "missing_context": [], "slow_start_context": [],
            "automation_candidates": [], "git_workflow_errors": [],
            "hook_errors": [], "tool_failures": [],
        }
        recs = synthesizer.generate(findings)
        self.assertEqual(len(recs), 0)  # below min_count=3

    def test_hook_errors_target_hook_doctor(self):
        findings = {
            "summary": {"sessions_analyzed": 5, "total_user_messages": 100},
            "corrections": [], "missing_context": [], "slow_start_context": [],
            "automation_candidates": [], "git_workflow_errors": [],
            "hook_errors": [{
                "hook_name": "SessionStart", "exit_code": 127,
                "stderr": "command not found", "command": "bad.sh",
                "session_count": 3,
            }],
            "tool_failures": [],
        }
        recs = synthesizer.generate(findings)
        hook_recs = [r for r in recs if r.target == "hook-doctor"]
        self.assertEqual(len(hook_recs), 1)
        self.assertIn("hook-doctor", hook_recs[0].proposed_rule.lower())

    def test_sorts_by_tokens_saved(self):
        findings = {
            "summary": {"sessions_analyzed": 5, "total_user_messages": 100},
            "corrections": [
                {"pattern": "p1", "category": "corrections", "count": 10, "sessions": 5,
                 "top_project": "test", "examples": ["msg"], "preceding_action": "did x"},
                {"pattern": "p2", "category": "corrections", "count": 3, "sessions": 2,
                 "top_project": "test", "examples": ["msg"], "preceding_action": "did y"},
            ],
            "missing_context": [], "slow_start_context": [],
            "automation_candidates": [], "git_workflow_errors": [],
            "hook_errors": [], "tool_failures": [],
        }
        recs = synthesizer.generate(findings)
        self.assertGreaterEqual(recs[0].estimated_tokens_saved, recs[-1].estimated_tokens_saved)
