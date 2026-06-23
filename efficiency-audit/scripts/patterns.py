#!/usr/bin/env python3
"""Regex matching engine — detects 5 friction categories in user messages."""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# --- Data types -----------------------------------------------------------------

@dataclass
class FindingGroup:
    pattern: str
    category: str
    count: int
    sessions: int
    top_project: str = ""
    examples: list[str] = field(default_factory=list)
    preceding_action: str | None = None


# --- Regex pattern sets ---------------------------------------------------------

CORRECTION_PATTERNS = [
    r"\bno[,!]?\s+(don'?t|do not|stop|never)\b",
    r"\b(don'?t|do not|stop|never|avoid)\s+(do(ing)?|use|run|add|create|write)\b",
    r"\b(wrong|incorrect|not (right|what I|what we))\b",
    r"\b(I said|I told you|as I mentioned|like I said)\b",
    r"\b(that'?s not|that is not)\s+what\b",
    r"\bplease (don'?t|do not|stop|never)\b",
    r"\b(revert|undo|go back)\b",
    r"\binstead[,\s]+(use|do|run|write)\b",
    r"\b(you should|you need to|you must)\s+not\b",
]

CONTEXT_REQUEST_PATTERNS = [
    r"\b(remember|recall|as I said|as we discussed|from (last|previous|earlier))\b",
    r"\b(context is|the situation is|for context|to clarify)\b",
    r"\b(I('?ve| have) (told|explained|mentioned|said) (you |this |before|already))\b",
    r"\b(again,? (this|the|we|I))\b",
    r"\b(same as|same pattern|same approach)\b",
]

SLOW_START_PATTERNS = [
    r"\b(first[,\s]+(let'?s?|you should|read|check|look at))\b",
    r"\b(before (you|we) (start|begin|do|proceed))\b",
    r"\b(the project (is|uses|has)|this repo(sitory)? (is|uses|has))\b",
    r"\b(we use|we don'?t use|in this project)\b",
    r"\b(always use|never use|make sure (you )?use)\b",
]

GIT_WORKFLOW_PATTERNS = [
    r"\b(pr|pull request).{0,40}(shows?|has|changed|touched).{0,20}\d+\s+files\b",
    r"\bout.of.date with (the )?base branch\b",
    r"\b(stale|wrong|old|outdated).{0,20}(remote|ref|origin|base)\b",
    r"\borigin/.{0,30}(stale|wrong|old)\b",
    r"\b(cascade|cherry.pick|rebase).{0,40}(wrong|incorrect|redo|fix|issue|failed)\b",
]

AUTOMATION_PATTERNS = [
    r"\b(every time|always (run|check|do|use)|each time|whenever)\b",
    r"\b(after (each|every) (commit|push|build|test))\b",
    r"\b(before (committing|pushing|building|testing|merging))\b",
    r"\b(automate|automating)\b",
    r"\b(set up|add|create|write|make) a (hook|alias|shortcut|script|command)\b",
]

CATEGORY_PATTERN_MAP = {
    "corrections": CORRECTION_PATTERNS,
    "context_requests": CONTEXT_REQUEST_PATTERNS,
    "slow_start": SLOW_START_PATTERNS,
    "automation": AUTOMATION_PATTERNS,
    "git_workflow": GIT_WORKFLOW_PATTERNS,
}

CATEGORY_SCORE_KEY = {
    "corrections": "corrections",
    "missing_context": "context_requests",
    "slow_start_context": "slow_start",
    "automation_candidates": "automation",
    "git_workflow_errors": "git_workflow",
}


# --- Noise filter (imported from scanner, re-exported for convenience) ----------

from scanner import _is_noise  # noqa: E402 — re-export


# --- Scoring --------------------------------------------------------------------

def score_message(text: str) -> dict[str, list[str]]:
    """Run all pattern sets against a message. Returns matched patterns per category."""
    return {
        key: [pat for pat in patterns if re.search(pat, text, re.IGNORECASE)]
        for key, patterns in CATEGORY_PATTERN_MAP.items()
    }


def group_by_pattern(items: list[dict], category: str) -> list[FindingGroup]:
    """Cluster scored items by first-matched pattern.

    First-pattern-wins prevents double-counting across categories.
    """
    groups: dict[str, dict] = {}
    for item in items:
        pat = item["patterns"][0]
        g = groups.setdefault(pat, {
            "_sessions": set(),
            "_projects": Counter(),
            "examples": [],
            "preceding_action": None,
        })
        g["_sessions"].add(item["session"])
        g["_projects"][item.get("project", "")] += 1
        if item.get("text") and len(g["examples"]) < 3:
            g["examples"].append(" ".join(item["text"].split())[:200])
        if g["preceding_action"] is None and item.get("preceding_action"):
            g["preceding_action"] = item["preceding_action"][:200]

    result = []
    for pat, g in groups.items():
        count = sum(g["_projects"].values())
        result.append(FindingGroup(
            pattern=pat,
            category=category,
            count=count,
            sessions=len(g["_sessions"]),
            top_project=g["_projects"].most_common(1)[0][0] if g["_projects"] else "",
            examples=g["examples"],
            preceding_action=g.get("preceding_action"),
        ))
    result.sort(key=lambda x: (x.count, x.sessions), reverse=True)
    return result


# --- Full analysis --------------------------------------------------------------

def analyze(sessions) -> dict:
    """Run full analysis: score all messages, group by pattern, aggregate tool/hook errors."""
    findings = {
        "summary": {
            "sessions_analyzed": len(sessions),
            "total_user_messages": 0,
            "date_range": {"earliest": None, "latest": None},
            "projects": Counter(),
        },
        "corrections": [],
        "missing_context": [],
        "slow_start_context": [],
        "automation_candidates": [],
        "git_workflow_errors": [],
        "hook_errors": [],
        "tool_failures": [],
    }

    all_timestamps = []
    scored = {key: [] for key in CATEGORY_SCORE_KEY}

    for sess in sessions:
        proj = sess.project
        findings["summary"]["projects"][proj] += 1

        for msg in sess.user_messages:
            findings["summary"]["total_user_messages"] += 1
            if msg.timestamp:
                all_timestamps.append(msg.timestamp)

            scores = score_message(msg.text)
            for cat, score_key in CATEGORY_SCORE_KEY.items():
                if scores[score_key]:
                    scored[cat].append({
                        "text": msg.text,
                        "session": sess.session_id,
                        "project": proj,
                        "patterns": scores[score_key],
                        "preceding_action": msg.preceding_action,
                    })

        for he in sess.hook_errors:
            findings["hook_errors"].append({
                "hook_name": he.hook_name, "exit_code": he.exit_code,
                "stderr": he.stderr, "command": he.command,
                "session": he.session,
            })

        for tf in sess.tool_failures:
            findings["tool_failures"].append({
                "tool": tf.tool, "error_category": tf.error_category,
                "error_text": tf.error_text, "session": tf.session,
            })

    for cat in CATEGORY_SCORE_KEY:
        findings[cat] = group_by_pattern(scored[cat], cat)

    if all_timestamps:
        all_timestamps.sort()
        findings["summary"]["date_range"]["earliest"] = all_timestamps[0]
        findings["summary"]["date_range"]["latest"] = all_timestamps[-1]

    findings["tool_failures"] = _aggregate_tool_failures(findings["tool_failures"])
    findings["hook_errors"] = _dedupe_hook_errors(findings["hook_errors"])

    return findings


def _aggregate_tool_failures(raw_failures: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for tf in raw_failures:
        key = (tf["tool"], tf["error_category"])
        g = groups.setdefault(key, {"tool": tf["tool"], "error_category": tf["error_category"],
                                     "count": 0, "_sessions": set(), "examples": []})
        g["count"] += 1
        g["_sessions"].add(tf.get("session", ""))
        if len(g["examples"]) < 3:
            g["examples"].append(" ".join(tf.get("error_text", "").split()))
    return sorted(
        [{"tool": g["tool"], "error_category": g["error_category"],
          "count": g["count"], "sessions": len(g["_sessions"]), "examples": g["examples"]}
         for g in groups.values()],
        key=lambda x: (x["count"], x["sessions"]), reverse=True,
    )


def _dedupe_hook_errors(errors: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for he in errors:
        key = he.get("command", "") or he.get("hook_name", "")
        if key not in seen:
            seen[key] = {**he, "_sessions": set()}
        if he.get("session"):
            seen[key]["_sessions"].add(he["session"])
    out = []
    for entry in seen.values():
        entry["session_count"] = len(entry.pop("_sessions"))
        out.append(entry)
    return out


# --- Baseline / delta -----------------------------------------------------------

BASELINE_PATH = Path("~/.claude/efficiency-audit-baseline.json").expanduser()


def _baseline_key(project_filter: str | None) -> str:
    return project_filter or "global"


def load_baseline(project_filter: str | None) -> dict | None:
    key = _baseline_key(project_filter)
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return data.get(key)
    except (OSError, json.JSONDecodeError):
        return None


def save_baseline(findings: dict, project_filter: str | None):
    key = _baseline_key(project_filter)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data[key] = {
            "saved_at": datetime.now(tz=timezone.utc).isoformat(),
            "sessions_analyzed": findings["summary"]["sessions_analyzed"],
            "category_totals": {
                cat: sum(g.count if hasattr(g, 'count') else g.get("count", 0)
                         for g in findings.get(cat, []))
                for cat in CATEGORY_SCORE_KEY
            },
            "hook_error_count": len(findings["hook_errors"]),
            "tool_failure_count": sum(g.get("count", 0) for g in findings.get("tool_failures", [])),
        }
        BASELINE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def compute_deltas(findings: dict, baseline: dict | None) -> dict:
    if not baseline:
        return {}
    deltas = {}
    prev_totals = baseline.get("category_totals", {})
    for cat in CATEGORY_SCORE_KEY:
        current = sum(g.count if hasattr(g, 'count') else g.get("count", 0)
                      for g in findings.get(cat, []))
        previous = prev_totals.get(cat, 0)
        diff = current - previous
        pct = round(100 * diff / previous) if previous else None
        deltas[cat] = {"current": current, "previous": previous, "delta": diff, "pct_change": pct}
    return deltas
