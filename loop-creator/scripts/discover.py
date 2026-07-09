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
    """Find user messages repeated across >=3 sessions with Jaccard >= 0.7."""
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
    """Compute score for a candidate. Reads c, returns float. Does not modify c."""
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
    """Merge candidates that share evidence sessions using connected components."""
    all_candidates = list(repeated) + list(temporal)
    if not all_candidates:
        return []

    n = len(all_candidates)
    # Build adjacency: two candidates are connected if they share a session
    adj = {i: set() for i in range(n)}
    for i in range(n):
        si = set(all_candidates[i]["evidence_sessions"])
        for j in range(i + 1, n):
            sj = set(all_candidates[j]["evidence_sessions"])
            if si & sj:
                adj[i].add(j)
                adj[j].add(i)

    # Connected components via DFS
    visited = set()
    components = []
    for i in range(n):
        if i in visited:
            continue
        stack = [i]
        comp = set()
        while stack:
            v = stack.pop()
            if v in comp:
                continue
            comp.add(v)
            visited.add(v)
            stack.extend(adj[v] - comp)
        components.append(comp)

    # Merge each component
    merged = []
    for comp in components:
        members = [all_candidates[i] for i in comp]
        # Start with the first member, merge in the rest
        base = dict(members[0])
        sessions = set(base["evidence_sessions"])
        signals = list(base["signals"])
        best_cadence = base.get("cadence_hint")
        best_prompt = base.get("sample_prompt", "")
        for m in members[1:]:
            sessions |= set(m["evidence_sessions"])
            for sig in m["signals"]:
                if sig not in signals:
                    signals.append(sig)
            if m.get("cadence_hint") and not best_cadence:
                best_cadence = m["cadence_hint"]
            if len(m.get("sample_prompt", "")) > len(best_prompt):
                best_prompt = m["sample_prompt"]
        base["evidence_sessions"] = sorted(sessions)
        base["signals"] = signals
        base["cadence_hint"] = best_cadence
        base["sample_prompt"] = best_prompt
        base["score"] = _score_candidate(base)
        if base["score"] >= 3:
            merged.append(base)

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
