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
