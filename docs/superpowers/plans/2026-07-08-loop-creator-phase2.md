# Loop Creator Phase 2: Discovery Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a discovery entry path to the loop-creator wizard — scan Claude Code session transcripts for repeated manual tasks and surface them as pre-populated loop candidates.

**Architecture:** New `discover.py` script reads `~/.claude/projects/<project>/*.jsonl` transcripts, extracts user messages, detects two signal types (`repeated_prompt` via Jaccard similarity across sessions, `temporal_cue` via regex + cadence extraction), scores and ranks candidates, and returns them to SKILL.md. SKILL.md gains a ~30-line Discovery Entry Path section that invokes the scanner, presents candidates, and pre-populates Phase 1 questions from the chosen candidate. Existing wizard flow is unchanged.

**Tech Stack:** Python 3 stdlib only (`json`, `re`, `pathlib`, `collections`, `math`), `unittest` for tests.

## Global Constraints

- Scripts return content as strings/dicts — they NEVER write files directly
- All Python scripts use stdlib only — no pip dependencies
- Tests use `unittest` (not pytest) — run from `scripts/` directory: `python3 -m unittest test_*.py`
- Discovery is read-only — never modifies transcript files
- Discovery never auto-creates loops — user confirms at every step
- The existing 58 Phase 1 tests must continue to pass (no regression)
- v1 implements 2 signals only: `repeated_prompt` (weight 5), `temporal_cue` (weight 5)
- Score threshold ≥ 3 to surface a candidate
- Jaccard similarity ≥ 0.7 across ≥ 3 distinct sessions for `repeated_prompt`

---

### Task 1: Transcript Reader + Tokenizer

**Files:**
- Create: `loop-creator/scripts/discover.py` (transcript reading + tokenization only)
- Create: `loop-creator/scripts/test_discover.py` (reader tests)

**Interfaces:**
- Produces: `read_user_messages(days: int = 30, project: str | None = None) -> dict[str, list[str]]` — returns `{session_id: [message_text, ...]}` for all sessions in the window
- Produces: `tokenize(text: str) -> set[str]` — lowercase, split, strip punctuation, remove stop words and tokens < 3 chars
- Produces: `jaccard_similarity(a: set[str], b: set[str]) -> float` — |A ∩ B| / |A ∪ B|

- [ ] **Step 1: Write the failing tests**

Create `loop-creator/scripts/test_discover.py`:

```python
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
        self.assertIn("42", tokens)
        self.assertNotIn("#42", tokens)
        self.assertNotIn("!", tokens)

    def test_removes_short_tokens(self):
        tokens = tokenize("is it a go for PR #42")
        self.assertIn("for", tokens)
        self.assertIn("42", tokens)
        self.assertNotIn("is", tokens)   # stop word
        self.assertNotIn("it", tokens)   # stop word
        self.assertNotIn("a", tokens)    # < 3 chars
        self.assertNotIn("go", tokens)   # < 3 chars

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_discover.py -v 2>&1
```

Expected: FAIL — `ModuleNotFoundError: No module named 'discover'`

- [ ] **Step 3: Write minimal implementation**

Create `loop-creator/scripts/discover.py`:

```python
#!/usr/bin/env python3
"""
Discovery engine — scans Claude Code session transcripts for loop candidates.

v1 signals: repeated_prompt, temporal_cue.
"""
import json
import re
import string
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Stop words -----------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "because", "but", "and", "or",
    "if", "while", "about", "up", "down", "it", "its", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "him", "her", "they", "them", "what", "which", "who", "whom",
}

# --- Noise patterns (from efficiency-audit scanner) -----------------------

NOISE_PATTERNS = [
    r"this session is being continued from a previous conversation",
    r"^\s*<command-(name|message|args)>",
    r"^\s*<local-command-(stdout|caveat)>",
    r"^\s*you are a (security reviewer|subagent)\b",
    r"\breview this change for security vulnerabilities\b",
    r"^\s*provide a code review for the given pull request\b",
    r"^\s*base directory for this skill\b",
    r"^\s*##\s+context\s*[-–]",
    r"\breview the (test|script|command|tool|output|run) (run )?output and fix\b",
    r"\breview the output and fix\b",
]


def _is_noise(text: str) -> bool:
    """True if text is system-generated boilerplate or pasted tool output."""
    low = text.lower()
    for pat in NOISE_PATTERNS:
        if re.search(pat, low):
            return True
    stripped = text.strip()
    if stripped.startswith("```"):
        return True
    return False


def _join_text(content) -> str:
    """Normalize message content (str or list of blocks) to plain text."""
    if isinstance(content, list):
        parts = [
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        return " ".join(parts)
    return content or ""


# --- Tokenization ---------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Tokenize text: lowercase, strip punctuation, remove stop words and short tokens."""
    text = text.lower().strip()
    text = text.translate(str.maketrans("", "", string.punctuation))
    tokens = text.split()
    return {t for t in tokens if len(t) >= 3 and t not in STOP_WORDS}


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|. Returns 0.0 for empty union."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


# --- Transcript reading ---------------------------------------------------

def _project_matches(project_dir: str, project_filter: str) -> bool:
    """Substring match for project name."""
    norm = lambda s: re.sub(r"[/.]", "-", s)
    return project_filter in project_dir or norm(project_filter) in norm(project_dir)


def read_user_messages(
    days: int = 30,
    project: str | None = None,
) -> dict[str, list[str]]:
    """Read all user messages from recent transcripts.

    Returns:
        {session_id: [message_text, ...]} for sessions with user messages.
    """
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return {}

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    results: dict[str, list[str]] = {}

    for f in sorted(base.rglob("*.jsonl")):
        if project and not _project_matches(str(f.parent), project):
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                continue
        except OSError:
            continue

        messages: list[str] = []
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if d.get("type") != "user":
                        continue
                    content = _join_text(d.get("message", {}).get("content", ""))
                    if content and not _is_noise(content):
                        messages.append(content)
        except OSError:
            continue

        if messages:
            results[f.stem] = messages

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_discover.py -v
```

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop-creator/scripts/discover.py loop-creator/scripts/test_discover.py
git commit -m "feat: add discover.py — transcript reader + tokenizer

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Signal Detectors + Scan Session Entry Point

**Files:**
- Modify: `loop-creator/scripts/discover.py` (add signal detection + scan_sessions)
- Modify: `loop-creator/scripts/test_discover.py` (add detector tests)

**Interfaces:**
- Produces: `detect_repeated_prompts(sessions: dict[str, list[str]]) -> list[dict]` — returns candidates from repeated prompts
- Produces: `extract_cadence(text: str) -> str | None` — extracts cadence string from temporal phrases
- Produces: `detect_temporal_cues(sessions: dict[str, list[str]]) -> list[dict]` — returns candidates from temporal patterns
- Produces: `scan_sessions(days: int = 30, project: str | None = None, max_candidates: int = 5) -> list[dict]` — main entry point

- [ ] **Step 1: Write the failing tests**

Append to `loop-creator/scripts/test_discover.py`:

```python
from discover import (
    detect_repeated_prompts,
    extract_cadence,
    detect_temporal_cues,
    scan_sessions,
)


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
            "s1": ["check if CI passed for PR #42"],
            "s2": ["check if CI passed for pull request 42"],
            "s3": ["check the CI status for PR 42"],
            "s4": ["completely different topic here"],
        }
        candidates = detect_repeated_prompts(sessions)
        self.assertGreaterEqual(len(candidates), 1)
        c = candidates[0]
        self.assertIn("repeated_prompt", c["signals"])
        self.assertGreaterEqual(len(c["evidence_sessions"]), 3)

    def test_excludes_pair_below_threshold(self):
        """Only 2 sessions with similar prompts — below ≥3 threshold."""
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
        proj_dir.mkdir(parents=True)
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
        we need ≥3 sessions for the repeated_prompt signal. Two sessions 
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_discover.py -v 2>&1 | tail -5
```

Expected: FAIL — `ImportError: cannot import name 'detect_repeated_prompts'`

- [ ] **Step 3: Write implementation**

Append to `loop-creator/scripts/discover.py`:

```python
# --- Cadence extraction ---------------------------------------------------

CADENCE_PATTERNS = [
    (r"every\s+(\d+)\s*minutes?", lambda m: f"{m.group(1)}m"),
    (r"every\s+half\s*hour", lambda m: "30m"),
    (r"every\s+hour|hourly", lambda m: "1h"),
    (r"every\s+morning|daily|each\s+day|before\s+standup", lambda m: "24h"),
    (r"each\s+friday|weekly|every\s+week", lambda m: "7d"),
]

EVENT_PATTERNS = [
    r"after\s+every\s+PR",
    r"on\s+new\s+pull\s+request",
    r"per\s+pull\s+request",
    r"when\s+a\s+PR\s+is",
    r"on\s+every\s+commit",
    r"when\s+CI\s+fails",
]


def extract_cadence(text: str) -> str | None:
    """Extract a cadence string from temporal phrases. Returns None if no match."""
    low = text.lower()
    for pat in EVENT_PATTERNS:
        if re.search(pat, low):
            return None  # event-driven, not time-based
    for pat, fn in CADENCE_PATTERNS:
        m = re.search(pat, low)
        if m:
            return fn(m)
    return None


# --- Signal: repeated_prompt -----------------------------------------------

REPEATED_PROMPT_WEIGHT = 5
REPEATED_MIN_SESSIONS = 3
JACCARD_THRESHOLD = 0.7


def detect_repeated_prompts(
    sessions: dict[str, list[str]],
) -> list[dict]:
    """Find user messages repeated across ≥3 sessions with Jaccard ≥ 0.7."""
    # Build list of (session_id, message_text, tokens) for all user messages
    all_msgs: list[tuple[str, str, set[str]]] = []
    for sid, msgs in sessions.items():
        for msg in msgs:
            tokens = tokenize(msg)
            if tokens:  # skip empty messages after tokenization
                all_msgs.append((sid, msg, tokens))

    # Group similar messages across distinct sessions
    candidates: list[dict] = []
    seen_pairs: set[tuple[int, int]] = set()

    for i in range(len(all_msgs)):
        for j in range(i + 1, len(all_msgs)):
            if (i, j) in seen_pairs:
                continue
            sid_i, msg_i, tok_i = all_msgs[i]
            sid_j, msg_j, tok_j = all_msgs[j]
            if sid_i == sid_j:
                continue  # same session — not "repeated across sessions"
            sim = jaccard_similarity(tok_i, tok_j)
            if sim < JACCARD_THRESHOLD:
                continue

            # Found a pair — grow the cluster
            cluster_sessions = {sid_i, sid_j}
            cluster_msgs = [msg_i, msg_j]
            cluster_indices = {i, j}
            seen_pairs.add((i, j))

            for k in range(len(all_msgs)):
                if k in cluster_indices:
                    continue
                sid_k, msg_k, tok_k = all_msgs[k]
                if sid_k in cluster_sessions:
                    continue  # already have this session
                # Check similarity to any message already in cluster
                for _, _, existing_tok in [all_msgs[idx] for idx in cluster_indices]:
                    if jaccard_similarity(tok_k, existing_tok) >= JACCARD_THRESHOLD:
                        cluster_sessions.add(sid_k)
                        cluster_msgs.append(msg_k)
                        cluster_indices.add(k)
                        break

            if len(cluster_sessions) >= REPEATED_MIN_SESSIONS:
                # Use the longest message as sample_prompt
                sample = max(cluster_msgs, key=len)
                # Derive a goal from the sample
                first = next((m for m in cluster_msgs if len(m.split()) >= 3), sample)
                goal = first[:80].strip()
                if len(first) > 80:
                    goal = goal.rsplit(" ", 1)[0] + "..."

                candidates.append({
                    "goal": goal,
                    "cadence_hint": None,
                    "context_hint": None,
                    "action_hint": sample,
                    "verify_hint": None,
                    "risk_hint": "read-only",
                    "signals": ["repeated_prompt"],
                    "evidence_sessions": sorted(cluster_sessions),
                    "sample_prompt": sample,
                })

    return candidates


# --- Signal: temporal_cue ---------------------------------------------------

TEMPORAL_CUE_WEIGHT = 5

TEMPORAL_PHRASES = [
    r"every\s+morning",
    r"every\s+day|daily|each\s+day",
    r"every\s+\d+\s*minutes?",
    r"every\s+half\s*hour",
    r"every\s+hour|hourly",
    r"each\s+friday|weekly|every\s+week",
    r"before\s+standup",
    r"end\s+of\s+day",
    r"each\s+morning\s+at",
]


def detect_temporal_cues(
    sessions: dict[str, list[str]],
) -> list[dict]:
    """Find messages with temporal phrases indicating a recurring cadence."""
    # Group messages by cadence
    cadence_groups: dict[str, dict] = defaultdict(lambda: {
        "sessions": set(),
        "messages": [],
        "cadence": None,
    })

    for sid, msgs in sessions.items():
        for msg in msgs:
            low = msg.lower()
            for phrase_pat in TEMPORAL_PHRASES:
                if re.search(phrase_pat, low):
                    cad = extract_cadence(msg)
                    if cad is None:
                        # Event-driven — skip for v1
                        continue
                    key = cad  # group by cadence string
                    cadence_groups[key]["sessions"].add(sid)
                    cadence_groups[key]["messages"].append(msg)
                    cadence_groups[key]["cadence"] = cad
                    break

    candidates = []
    for cad, group in cadence_groups.items():
        if len(group["sessions"]) < 2:
            continue  # need at least 2 sessions with temporal pattern
        sample = max(group["messages"], key=len)
        first = next((m for m in group["messages"] if len(m.split()) >= 3), sample)
        goal = first[:80].strip()
        if len(first) > 80:
            goal = goal.rsplit(" ", 1)[0] + "..."

        candidates.append({
            "goal": goal,
            "cadence_hint": group["cadence"],
            "context_hint": None,
            "action_hint": sample,
            "verify_hint": None,
            "risk_hint": "read-only",
            "signals": ["temporal_cue"],
            "evidence_sessions": sorted(group["sessions"]),
            "sample_prompt": sample,
        })

    return candidates


# --- Scoring & ranking -----------------------------------------------------

def _score_candidate(c: dict) -> float:
    """Compute score for a candidate. Modifies c in place to merge signals."""
    score = 0.0
    if "repeated_prompt" in c["signals"]:
        score += REPEATED_PROMPT_WEIGHT
    if "temporal_cue" in c["signals"]:
        score += TEMPORAL_CUE_WEIGHT
    if len(c["evidence_sessions"]) >= 3:
        score += 1  # bonus for strong evidence
    if c["cadence_hint"] is not None:
        score += 1  # bonus for pre-filled cadence
    return score


def _merge_candidates(
    repeated: list[dict],
    temporal: list[dict],
) -> list[dict]:
    """Merge repeated-prompt and temporal-cue candidates that overlap."""
    all_candidates = list(repeated) + list(temporal)

    # Simple overlap: if two candidates share ≥1 session, merge them
    merged = []
    used = set()
    for i, c1 in enumerate(all_candidates):
        if i in used:
            continue
        merged_c = dict(c1)
        merged_c["evidence_sessions"] = set(c1["evidence_sessions"])
        merged_c["signals"] = list(c1["signals"])
        for j, c2 in enumerate(all_candidates):
            if j <= i or j in used:
                continue
            if merged_c["evidence_sessions"] & set(c2["evidence_sessions"]):
                # Merge c2 into merged_c
                merged_c["evidence_sessions"] |= set(c2["evidence_sessions"])
                for sig in c2["signals"]:
                    if sig not in merged_c["signals"]:
                        merged_c["signals"].append(sig)
                if c2["cadence_hint"] and not merged_c.get("cadence_hint"):
                    merged_c["cadence_hint"] = c2["cadence_hint"]
                if len(c2.get("sample_prompt", "")) > len(merged_c.get("sample_prompt", "")):
                    merged_c["sample_prompt"] = c2["sample_prompt"]
                used.add(j)
        merged_c["evidence_sessions"] = sorted(merged_c["evidence_sessions"])
        merged_c["score"] = _score_candidate(merged_c)
        if merged_c["score"] >= 3:
            merged.append(merged_c)
        used.add(i)

    return sorted(merged, key=lambda c: c["score"], reverse=True)


# --- Public API ------------------------------------------------------------

def scan_sessions(
    days: int = 30,
    project: str | None = None,
    max_candidates: int = 5,
) -> list[dict]:
    """Scan session transcripts and return ranked loop candidates.

    Returns list of dicts sorted by score descending, capped at max_candidates.
    Only candidates with score >= 3 are returned.
    """
    sessions = read_user_messages(days=days, project=project)
    if not sessions:
        return []

    repeated = detect_repeated_prompts(sessions)
    temporal = detect_temporal_cues(sessions)

    candidates = _merge_candidates(repeated, temporal)

    # Cap and rank
    top = candidates[:max_candidates]
    for i, c in enumerate(top):
        c["rank"] = i + 1

    return top
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_discover.py -v
```

Expected: all tests PASS (13 original + ~16 new = ~29 tests)

- [ ] **Step 5: Run full suite to verify no regression**

```bash
cd loop-creator/scripts && python3 -m unittest discover -p "test_*.py" -v 2>&1 | tail -3
```

Expected: all tests PASS (58 + ~29 = ~87 tests)

- [ ] **Step 6: Commit**

```bash
git add loop-creator/scripts/discover.py loop-creator/scripts/test_discover.py
git commit -m "feat: add signal detectors + scan_sessions entry point

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: SKILL.md — Discovery Entry Path

**Files:**
- Modify: `loop-creator/skills/loop-creator/SKILL.md` (insert discovery section before Phase 1)

**Interfaces:**
- Consumes: `discover.scan_sessions` — invoked via JSON-over-stdin pattern
- Produces: New "Discovery Entry Path" section in SKILL.md

- [ ] **Step 1: Insert discovery section into SKILL.md**

Read the current SKILL.md. Insert the following section between the "## Flow" section and the "## Interview Questions" section (after line 18, before line 20):

```markdown
## Discovery Entry Path

Triggered by: "discover loops," "what can I automate," "find loop candidates," "what should I turn into a loop," "any tasks I could hand off to a loop."

### Step 1: Scan transcripts

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
CURRENT_PROJECT=$(git -C "$(pwd)" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||')
[ -z "$CURRENT_PROJECT" ] && CURRENT_PROJECT=$(basename "$(pwd)")
echo "{\"days\":30,\"project\":\"$CURRENT_PROJECT\"}" | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from discover import scan_sessions
d = json.loads(sys.stdin.read())
candidates = scan_sessions(days=d.get('days', 30), project=d.get('project'))
print(json.dumps(candidates))
"
```

### Step 2: Present candidates

If 0 candidates: "Nothing obvious found in your last 30 days. Want to create a loop from scratch?" → jump to Phase 1.

If 1+ candidates: Show each with rank, score, goal, and a one-line evidence summary:

```
Here's what I found in your recent sessions:

1. CI Status Monitor (score 8.5)
   Found you checking CI status in 5 sessions over 14 days.
   Sample: "check if PR #42's CI passed"

2. Daily Project Review (score 6.0)
   Found "every morning" + workspace inspection pattern in 3 sessions.
   Sample: "what changed in the repo since yesterday"

Pick a number, or say "from scratch" to design your own, or "show more."
```

### Step 3: Pre-populate Phase 1

When user picks a candidate, replace Q1-Q6 with confirmation variants using the candidate's hints:

| Q | Discovery mode (candidate selected) |
|---|-------------------------------------|
| Q1 | "I found you {sample_prompt} across {N} sessions. Create a '{goal}' loop?" |
| Q2 | If `cadence_hint` set: "I see a {cadence_hint} pattern. Keep that?" If None: ask original Q2 |
| Q3 | If `verify_hint` set: "You typically verify by {verify_hint}. Use that?" If None: ask original Q3 |
| Q4 | "You access {context_hint or 'local files'}. Anything else?" |
| Q5 | "You usually stop after one check. Escalate on failure?" (default; adjust per signal type) |
| Q6 | "{risk_hint or 'read-only'}. Any risk I'm missing?" |

Phases 2 and 3 (Q7-Q11) are asked fresh — discovery doesn't cover per-iteration details.

If the user says "from scratch" at Step 2, skip to Phase 1 as normal.

If the user says "show more," increase `max_candidates` to 10 and re-run the scan.
```

- [ ] **Step 2: Verify SKILL.md frontmatter integrity**

```bash
head -4 loop-creator/skills/loop-creator/SKILL.md
```

Expected: YAML frontmatter starts and ends correctly with `---`

- [ ] **Step 3: Run full test suite to confirm no regression**

```bash
cd loop-creator/scripts && python3 -m unittest discover -p "test_*.py" -v 2>&1 | tail -3
```

Expected: all tests PASS

- [ ] **Step 4: Verify SKILL.md line count is reasonable**

```bash
wc -l loop-creator/skills/loop-creator/SKILL.md
```

Expected: ~140 lines (up from 103, within the ~30-line target for discovery section)

- [ ] **Step 5: Commit**

```bash
git add loop-creator/skills/loop-creator/SKILL.md
git commit -m "feat: add discovery entry path to SKILL.md

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Integration Validation

**Files:**
- Modify: (none — validation only)

**Interfaces:**
- Consumes: all Phase 1 + Phase 2 scripts and SKILL.md
- Produces: test output confirming all pieces work together

- [ ] **Step 1: Run full test suite**

```bash
cd loop-creator/scripts && python3 -m unittest discover -v -p "test_*.py" 2>&1 | tail -5
```

Expected: all tests PASS (~87 tests across 5 test files)

- [ ] **Step 2: Verify plugin structure**

```bash
echo "=== Plugin structure ===" && find loop-creator -type f -not -path '*__pycache__*' | sort && echo "" && echo "=== plugin.json valid? ===" && python3 -c "import json; json.load(open('loop-creator/.claude-plugin/plugin.json')); print('YES')" && echo "" && echo "=== SKILL.md sections ===" && grep "^## " loop-creator/skills/loop-creator/SKILL.md
```

Expected: All files present, plugin.json valid, SKILL.md sections include "Discovery Entry Path" alongside existing sections.

- [ ] **Step 3: End-to-end scan with sample transcripts**

```bash
cd loop-creator/scripts && python3 -c "
import json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone
from discover import scan_sessions

# Create temp transcripts with known patterns
tmp = tempfile.mkdtemp()
old_home = os.environ.get('HOME', '')
os.environ['HOME'] = tmp

proj_dir = Path(tmp) / '.claude' / 'projects' / 'e2e-test'
proj_dir.mkdir(parents=True)

# 4 sessions with CI check pattern
for i in range(4):
    path = proj_dir / f'session-{i:03d}.jsonl'
    with open(path, 'w') as f:
        f.write(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': 'check if CI passed for PR #42'}}) + '\n')
    now = datetime.now(tz=timezone.utc).timestamp()
    os.utime(path, (now, now))

candidates = scan_sessions(days=30)
assert len(candidates) >= 1, f'Expected at least 1 candidate, got {len(candidates)}'
c = candidates[0]
assert c['score'] >= 3, f'Score too low: {c[\"score\"]}'
assert 'repeated_prompt' in c['signals']
assert len(c['evidence_sessions']) >= 3
print(f'E2E PASSED: found candidate with score {c[\"score\"]} — {c[\"goal\"]}')
print(f'  Signals: {c[\"signals\"]}')
print(f'  Sessions: {c[\"evidence_sessions\"]}')

# Cleanup
os.environ['HOME'] = old_home
"
```

Expected: "E2E PASSED" with candidate details

- [ ] **Step 4: Verify all existing tests still pass (regression check)**

```bash
cd loop-creator/scripts && python3 -m unittest discover -v -p "test_*.py" 2>&1 | grep -E "^(Ran|FAILED|OK)"
```

Expected: "Ran N tests ... OK" with no failures

- [ ] **Step 5: Commit**

```bash
git add -A && git status
```

Verify only loop-creator files are staged, then:

```bash
git commit -m "feat: complete Phase 2 discovery engine with integration validation

Co-Authored-By: Claude <noreply@anthropic.com>"
```
