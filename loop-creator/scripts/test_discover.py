#!/usr/bin/env python3
"""Tests for discover — transcript reader + tokenizer."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from discover import (
    read_user_messages,
    tokenize,
    jaccard_similarity,
    detect_repeated_prompts,
    extract_cadence,
    detect_temporal_cues,
    scan_sessions,
)


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


class ExtractCadenceTests(unittest.TestCase):
    def test_daily_patterns(self):
        self.assertEqual(extract_cadence("check every morning"), "24h")
        self.assertEqual(extract_cadence("daily review"), "24h")
        self.assertEqual(extract_cadence("each day I do this"), "24h")
        self.assertEqual(extract_cadence("before standup I check"), "24h")

    def test_minute_patterns(self):
        self.assertEqual(extract_cadence("every 30 minutes check"), "30m")
        self.assertEqual(extract_cadence("check every half hour"), "30m")

    def test_hourly_patterns(self):
        self.assertEqual(extract_cadence("check every hour"), "1h")
        self.assertEqual(extract_cadence("hourly status update"), "1h")

    def test_weekly_patterns(self):
        self.assertEqual(extract_cadence("each Friday review"), "7d")
        self.assertEqual(extract_cadence("weekly summary"), "7d")
        self.assertEqual(extract_cadence("every week check"), "7d")

    def test_event_driven_patterns(self):
        """Event-driven patterns map to None (not time-based)."""
        self.assertIsNone(extract_cadence("after every PR merged"))
        self.assertIsNone(extract_cadence("on new pull request"))

    def test_no_temporal_cue(self):
        self.assertIsNone(extract_cadence("check if CI passed"))
        self.assertIsNone(extract_cadence("what is the status"))


class DetectRepeatedPromptsTests(unittest.TestCase):
    def test_finds_repeated_across_sessions(self):
        sessions = {
            "s1": ["please check CI build status for project forty-two"],
            "s2": ["please check CI build pipeline for project forty-two"],
            "s3": ["please check CI build status for pipeline forty-two"],
            "s4": ["completely different topic here"],
        }
        candidates = detect_repeated_prompts(sessions)
        self.assertGreaterEqual(len(candidates), 1)
        c = candidates[0]
        self.assertIn("repeated_prompt", c["signals"])
        self.assertGreaterEqual(len(c["evidence_sessions"]), 3)

    def test_excludes_pair_below_threshold(self):
        """Only 2 sessions with similar prompts — below >=3 threshold."""
        sessions = {
            "s1": ["check CI status"],
            "s2": ["check CI status"],
            "s3": ["different topic"],
        }
        candidates = detect_repeated_prompts(sessions)
        self.assertEqual(len(candidates), 0)

    def test_excludes_dissimilar_content(self):
        """All unique messages — no clusters form."""
        sessions = {
            "s1": ["check CI status"],
            "s2": ["review the README"],
            "s3": ["deploy to staging"],
            "s4": ["update dependencies"],
        }
        candidates = detect_repeated_prompts(sessions)
        self.assertEqual(len(candidates), 0)


class DetectTemporalCuesTests(unittest.TestCase):
    def test_finds_temporal_patterns(self):
        sessions = {
            "s1": ["every morning I check what changed"],
            "s2": ["daily review of the project"],
            "s3": ["completely unrelated topic"],
        }
        candidates = detect_temporal_cues(sessions)
        self.assertGreaterEqual(len(candidates), 1)
        c = candidates[0]
        self.assertIn("temporal_cue", c["signals"])
        self.assertIsNotNone(c["cadence_hint"])

    def test_merges_same_cadence_patterns(self):
        """Multiple sessions mentioning 'daily' should merge into one candidate."""
        sessions = {
            "s1": ["every morning review"],
            "s2": ["daily status check"],
            "s3": ["each day I inspect the repo"],
        }
        candidates = detect_temporal_cues(sessions)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["cadence_hint"], "24h")

    def test_no_temporal_cues_returns_empty(self):
        sessions = {
            "s1": ["check CI"],
            "s2": ["deploy now"],
        }
        candidates = detect_temporal_cues(sessions)
        self.assertEqual(len(candidates), 0)


class ScanSessionsIntegrationTests(unittest.TestCase):
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
        proj_dir.mkdir(parents=True, exist_ok=True)
        path = proj_dir / f"{sid}.jsonl"
        with open(path, "w") as f:
            for m in messages:
                f.write(json.dumps(m) + "\n")
        now = datetime.now(tz=timezone.utc).timestamp()
        os.utime(path, (now, now))

    def test_empty_transcripts_returns_empty_list(self):
        candidates = scan_sessions(days=30)
        self.assertEqual(candidates, [])

    def test_finds_repeated_prompt_candidate(self):
        for i in range(4):
            self._make(
                [{"type": "user", "message": {"role": "user", "content": "check if CI passed for PR #42"}}],
                sid=f"session-{i:03d}",
            )
        candidates = scan_sessions(days=30)
        self.assertGreaterEqual(len(candidates), 1)

    def test_finds_temporal_cue_candidate(self):
        for i in range(3):
            self._make(
                [{"type": "user", "message": {"role": "user", "content": "every morning I review what changed"}}],
                sid=f"session-{i:03d}",
            )
        candidates = scan_sessions(days=30)
        self.assertGreaterEqual(len(candidates), 1)

    def test_filters_below_score_threshold(self):
        """Two sessions with similar prompt and no temporal cue — score 5, but
        we need >=3 sessions for the repeated_prompt signal. Two sessions
        don't group, so no candidate."""
        for i in range(2):  # Only 2 sessions — below threshold
            self._make(
                [{"type": "user", "message": {"role": "user", "content": "check CI status"}}],
                sid=f"session-{i:03d}",
            )
        candidates = scan_sessions(days=30)
        self.assertEqual(len(candidates), 0)

    def test_respects_max_candidates(self):
        """Should cap at max_candidates."""
        # Create 10 different repeated-prompt patterns across 3 sessions each
        for pattern_idx in range(10):
            for sess_idx in range(3):
                self._make(
                    [{"type": "user", "message": {"role": "user", "content": f"check pattern {pattern_idx} status"}}],
                    sid=f"p{pattern_idx}-s{sess_idx:03d}",
                )
        candidates = scan_sessions(days=30, max_candidates=3)
        self.assertLessEqual(len(candidates), 3)

    def test_candidate_structure(self):
        """Verify the full candidate dict structure."""
        for i in range(4):
            self._make(
                [{"type": "user", "message": {"role": "user", "content": "every morning review project"}}],
                sid=f"session-{i:03d}",
            )
        candidates = scan_sessions(days=30)
        c = candidates[0]
        for key in ["rank", "score", "goal", "cadence_hint", "signals",
                     "evidence_sessions", "sample_prompt"]:
            self.assertIn(key, c)
        self.assertIsInstance(c["score"], (int, float))
        self.assertGreaterEqual(c["score"], 3)
        self.assertIsInstance(c["signals"], list)


if __name__ == "__main__":
    unittest.main()
