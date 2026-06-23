#!/usr/bin/env python3
"""Transcript parser — reads Claude Code JSONL session files."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path


# --- Data types -----------------------------------------------------------------

@dataclass
class UserMessage:
    text: str
    timestamp: str
    preceding_action: str | None = None


@dataclass
class HookError:
    hook_name: str
    exit_code: int | None
    stderr: str
    command: str
    session: str = ""


@dataclass
class ToolFailure:
    tool: str
    error_category: str
    error_text: str
    session: str = ""


@dataclass
class SessionData:
    path: str
    project: str
    session_id: str
    user_messages: list[UserMessage] = field(default_factory=list)
    hook_errors: list[HookError] = field(default_factory=list)
    tool_failures: list[ToolFailure] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)


# --- Noise patterns --------------------------------------------------------------

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
    return _is_tool_output_paste(text)


def _is_tool_output_paste(text: str) -> bool:
    """Detect messages dominated by pasted shell/test output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        return True
    first = next((l for l in stripped.splitlines() if l.strip()), "")
    if re.match(r"^\s*(python3?|bash|sh|node|ruby|go|cargo|make|cmake|\./|/)\s+\S", first):
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        common_verbs = {"please", "this", "that", "with", "from", "have", "will"}
        conversational = [w for w in words if w not in common_verbs]
        if len(conversational) < 8:
            return True
    return False


def _join_text(content) -> str:
    """Normalize message content (str or list of blocks) to plain text."""
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return " ".join(parts)
    return content or ""


# --- Tool failure classification ------------------------------------------------

def classify_tool_error(tool_name: str, error_text: str) -> str:
    """Classify a tool failure into one of 7 categories."""
    t = error_text.lower()
    if "file has not been read yet" in t or "read it first before writing" in t:
        return "unread_write"
    if "request interrupted by user" in t or "operation was cancelled" in t:
        return "user_interrupted"
    if "permission denied" in t:
        return "permission_denied"
    if ("pathspec" in t and "did not match" in t) or "no such file or directory" in t:
        return "file_not_found"
    if "not inside a" in t and "repository" in t:
        return "wrong_context"
    if "not a git repository" in t:
        return "wrong_context"
    m = re.search(r"exit code (\d+)", t)
    if m:
        return "git_error" if int(m.group(1)) == 128 else "bash_nonzero"
    return "tool_use_error"


# --- File discovery -------------------------------------------------------------

def _project_matches(parent_dir: str, project_filter: str) -> bool:
    """Substring match tolerant of / and . -> - encoding in transcript dirs."""
    norm = lambda s: re.sub(r"[/.]", "-", s)
    return project_filter in parent_dir or norm(project_filter) in norm(parent_dir)


def find_transcript_files(days: int = 30, project: str | None = None) -> list[Path]:
    """Find JSONL transcript files from the last N days, optionally filtered by project."""
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    results = []
    for f in base.rglob("*.jsonl"):
        if project and not _project_matches(str(f.parent), project):
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime >= cutoff:
                results.append(f)
        except OSError:
            pass
    return sorted(results, key=lambda f: f.stat().st_mtime, reverse=True)


# --- Session parsing ------------------------------------------------------------

def parse_session(path: Path) -> SessionData | None:
    """Parse one JSONL session file. Returns None on read failure."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return None

    session = SessionData(
        path=str(path),
        project=path.parent.name,
        session_id=path.stem,
    )

    last_assistant: str | None = None
    pending_tool_uses: dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue

        t = d.get("type", "")
        ts = d.get("timestamp", "")
        if ts:
            session.timestamps.append(ts)

        if t == "assistant":
            raw = d.get("message", {}).get("content", "")
            if isinstance(raw, list):
                for block in raw:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        pending_tool_uses[block["id"]] = block.get("name", "?")
            content = _join_text(raw)
            if content:
                last_assistant = " ".join(content.split())[:300]

        elif t == "user":
            raw = d.get("message", {}).get("content", "")
            if isinstance(raw, list):
                for block in raw:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result" and block.get("is_error"):
                        tool_name = pending_tool_uses.get(block.get("tool_use_id", ""), "?")
                        inner = block.get("content", [])
                        if isinstance(inner, list):
                            error_text = " ".join(c.get("text", "") for c in inner if isinstance(c, dict))
                        else:
                            error_text = str(inner)
                        session.tool_failures.append(ToolFailure(
                            tool=tool_name,
                            error_category=classify_tool_error(tool_name, error_text),
                            error_text=error_text[:300],
                            session=session.session_id,
                        ))
            content = _join_text(raw)
            if content and not _is_noise(content):
                session.user_messages.append(UserMessage(
                    text=content,
                    timestamp=ts,
                    preceding_action=last_assistant,
                ))

        elif t == "system":
            for he in d.get("hookErrors", []) or []:
                if isinstance(he, dict):
                    session.hook_errors.append(HookError(
                        hook_name=he.get("hookName", ""),
                        exit_code=he.get("exitCode"),
                        stderr=str(he.get("stderr", ""))[:200],
                        command=he.get("command", ""),
                        session=session.session_id,
                    ))

        elif t == "attachment":
            att = d.get("attachment", {})
            if isinstance(att, dict) and att.get("type") == "hook_non_blocking_error":
                session.hook_errors.append(HookError(
                    hook_name=att.get("hookName", ""),
                    exit_code=att.get("exitCode"),
                    stderr=str(att.get("stderr", ""))[:200],
                    command=att.get("command", ""),
                    session=session.session_id,
                ))

    return session


def parse_all(files: list[Path]) -> list[SessionData]:
    """Batch-parse transcript files. Skips unparseable files silently."""
    sessions = []
    for f in files:
        try:
            sess = parse_session(f)
            if sess and (sess.user_messages or sess.tool_failures or sess.hook_errors):
                sessions.append(sess)
        except Exception:
            pass  # skip malformed files
    return sessions
