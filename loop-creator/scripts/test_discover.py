#!/usr/bin/env python3
"""Tests for discover — transcript reader + tokenizer."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from discover import read_user_messages, tokenize, jaccard_similarity


def _make_transcript(messages: list[dict], project_name: str = "test-project") -> Path:
    """Create a temp JSONL transcript file in ~/.claude/projects/<project>/<session>.jsonl."""
    tmp_root = Path(tempfile.mkdtemp())
    proj_dir = tmp_root / ".claude" / "projects" / project_name
    proj_dir.mkdir(parents=True)
    path = proj_dir / "session-001.jsonl"
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    now = datetime.now(tz=timezone.utc).timestamp()
    os.utime(path, (now, now))
    # Return the tmp_root so tests can override HOME
    return tmp_root


class TokenizeTests(unittest.TestCase):
    def test_lowercase_and_split(self):
        tokens = tokenize("Check If CI Passed")
        self.assertIn("check", tokens)
        self.assertIn("passed", tokens)
        self.assertNotIn("If", tokens)  # stop word

    def test_strips_punctuation(self):
        tokens = tokenize("check if PR #42's CI passed!")
        self.assertIn("42s", tokens)     # punctuation removed but 's' stays
        self.assertNotIn("#42", tokens)
        self.assertNotIn("!", tokens)

    def test_removes_short_tokens(self):
        tokens = tokenize("is it a go for PR #42")
        self.assertNotIn("is", tokens)   # stop word
        self.assertNotIn("it", tokens)   # stop word
        self.assertNotIn("a", tokens)    # < 3 chars
        self.assertNotIn("go", tokens)   # < 3 chars
        self.assertNotIn("for", tokens)  # stop word
        self.assertNotIn("pr", tokens)   # < 3 chars
        self.assertNotIn("42", tokens)   # < 3 chars

    def test_empty_string_returns_empty_set(self):
        tokens = tokenize("")
        self.assertEqual(tokens, set())

    def test_all_stop_words_returns_empty_set(self):
        tokens = tokenize("the is a to of")
        self.assertEqual(tokens, set())


class JaccardTests(unittest.TestCase):
    def test_identical_sets(self):
        self.assertEqual(jaccard_similarity({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint_sets(self):
        self.assertEqual(jaccard_similarity({"a"}, {"b"}), 0.0)

    def test_partial_overlap(self):
        result = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        self.assertAlmostEqual(result, 2 / 4)  # intersect=2, union=4

    def test_empty_sets(self):
        self.assertEqual(jaccard_similarity(set(), set()), 0.0)


class ReadUserMessagesTests(unittest.TestCase):
    def setUp(self):
        self._old_home = os.environ.get("HOME")
        self.tmp = tempfile.mkdtemp()
        os.environ["HOME"] = self.tmp

    def tearDown(self):
        if self._old_home:
            os.environ["HOME"] = self._old_home
        else:
            os.environ.pop("HOME", None)

    def _make(self, messages, project="test-proj", sid="session-001"):
        proj_dir = Path(self.tmp) / ".claude" / "projects" / project
        proj_dir.mkdir(parents=True)
        path = proj_dir / f"{sid}.jsonl"
        with open(path, "w") as f:
            for m in messages:
                f.write(json.dumps(m) + "\n")
        now = datetime.now(tz=timezone.utc).timestamp()
        os.utime(path, (now, now))

    def test_extracts_user_messages_only(self):
        self._make([
            {"type": "user", "message": {"role": "user", "content": "check CI status"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "CI is green"}]}},
            {"type": "user", "message": {"role": "user", "content": "deploy to staging"}},
        ])
        result = read_user_messages(days=30)
        msgs = result.get("session-001", [])
        self.assertEqual(len(msgs), 2)
        self.assertIn("check CI status", msgs)
        self.assertIn("deploy to staging", msgs)

    def test_filters_noise_messages(self):
        """System-injected messages should be excluded."""
        self._make([
            {"type": "user", "message": {"role": "user", "content": "this session is being continued from a previous conversation"}},
            {"type": "user", "message": {"role": "user", "content": "review the output and fix the failing test"}},
            {"type": "user", "message": {"role": "user", "content": "check deploy status"}},
        ])
        result = read_user_messages(days=30)
        msgs = result.get("session-001", [])
        self.assertEqual(msgs, ["check deploy status"])

    def test_handles_list_content(self):
        """User messages with content as list of text blocks."""
        self._make([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "check CI status"}]}},
        ])
        result = read_user_messages(days=30)
        msgs = result.get("session-001", [])
        self.assertEqual(msgs, ["check CI status"])

    def test_empty_sessions_returns_empty(self):
        result = read_user_messages(days=30)
        self.assertEqual(result, {})

    def test_respects_days_filter(self):
        """Messages older than days should be excluded."""
        proj_dir = Path(self.tmp) / ".claude" / "projects" / "old-proj"
        proj_dir.mkdir(parents=True)
        path = proj_dir / "old-session.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "old message"}}) + "\n")
        old_time = (datetime.now(tz=timezone.utc) - timedelta(days=60)).timestamp()
        os.utime(path, (old_time, old_time))
        result = read_user_messages(days=30)
        self.assertNotIn("old-session", result)

    def test_filters_by_project(self):
        self._make([{"type": "user", "message": {"role": "user", "content": "msg A"}}], project="proj-a", sid="s1")
        self._make([{"type": "user", "message": {"role": "user", "content": "msg B"}}], project="proj-b", sid="s2")
        result = read_user_messages(days=30, project="proj-a")
        self.assertIn("s1", result)
        self.assertNotIn("s2", result)


if __name__ == "__main__":
    unittest.main()
