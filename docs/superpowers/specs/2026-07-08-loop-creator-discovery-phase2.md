# Loop Creator — Phase 2: Discovery Engine

**Date:** 2026-07-08
**Depends on:** Phase 1 loop-creator plugin (PR #1)
**Status:** Design approved, pending implementation plan

## Overview

Adds a discovery entry path to the loop-creator wizard. Instead of starting from a blank slate, users can ask the wizard to scan their Claude Code session history and surface tasks they're already doing manually that would benefit from loop automation. Discovered candidates pre-populate the interview, turning an 11-question flow into a 6-question confirmation flow.

## Architecture

### Integration Model

Discovery is a **front-end** to the existing wizard — it seeds the interview with evidence but does not change what the interview produces. The existing Phase 1-3 questions, tier detection, and all three generators remain untouched.

```
User says "discover loops I could automate"
    → discover.py scans ~/.claude/projects/<project>/*.jsonl
    → presents ranked candidates (top 5, score ≥ 3)
    → user picks one, or "start from scratch," or "show more"
    → Phase 1 interview (pre-populated with discovered context)
    → Phase 2-3 (unchanged)
    → Tier detection + output generation (unchanged)
```

### New Files

```
loop-creator/
├── scripts/
│   ├── discover.py          # NEW — transcript scanner + signal scoring
│   └── test_discover.py     # NEW — unit tests (≥12 test cases)
├── skills/loop-creator/
│   └── SKILL.md             # MODIFIED — add discovery entry path section
```

### Modified Files

`skills/loop-creator/SKILL.md`: Add a ~30-line section before the existing Phase 1. The discovery section describes:
- New trigger phrases
- How to invoke the scanner script
- How to present candidates and collect user choice
- How to pre-populate Phase 1 questions from the chosen candidate

Existing Phase 1-3, tier detection, and output generation sections are unchanged.

## Discovery Engine (`discover.py`)

### Interface

```python
def scan_sessions(
    days: int = 30,
    project: str | None = None,
    max_candidates: int = 5,
) -> list[dict]:
    """Return ranked loop candidates with evidence.
    
    Returns list of dicts sorted by score descending:
        {
            "rank": 1,
            "score": 8.5,
            "goal": "Monitor CI status for PRs",
            "cadence_hint": "30m",              # or None if undetected
            "context_hint": "CI run logs",       # or None
            "action_hint": "Check if build passed or failed",  # or None
            "verify_hint": "CI status matches actual build",  # or None
            "risk_hint": "read-only",            # or None
            "signals": ["repeated_prompt", "status_check"],
            "evidence_sessions": ["abc123", "def456", "ghi789"],
            "sample_prompt": "check if PR #42's CI passed",
        }
    """
```

### Signal Types

| Signal | Detection method | Weight | Example match |
|--------|-----------------|--------|---------------|
| `repeated_prompt` | Cosine similarity ≥ 0.7 of user messages across 3+ sessions | 5 | User says "check if PR #42's CI passed" in 4 sessions |
| `temporal_cue` | Regex match for cadence phrases | 5 | "every morning," "before standup," "each Friday," "daily," "weekly" |
| `status_check` | Regex match for status-check phrasing | 3 | "check if," "what's the status," "is it done," "did it pass," "any updates on" |
| `compounding_state` | User messages starting with "also," "additionally," "update the," "add to" referencing prior output | 3 | "Also add the new API endpoint to the report" |
| `manual_verification` | Run-cmd → read-output → confirm pattern within single session | 2 | `npm test` → "ok looks good" |

### Scoring

Each candidate has a `score` computed as:

```
score = sum(signal_weights for matched signals)
      + bonus for ≥3 evidence sessions (+1)
      + bonus for temporal_cue present (+1, cadence is pre-filled)
```

Candidates with score < 3 are filtered out. Results are ordered by score descending, capped at `max_candidates`.

### Cadence Extraction

When `temporal_cue` matches, extract the cadence string:

| User says | Extracted `cadence_hint` |
|-----------|--------------------------|
| "every morning" / "daily" / "each day" | `"24h"` |
| "every 30 minutes" / "every half hour" | `"30m"` |
| "every hour" / "hourly" | `"1h"` |
| "before standup" / "each morning at 9" | `"24h"` (nearest) |
| "each Friday" / "weekly" / "every week" | `"7d"` |
| "after every PR" / "on new PR" / "per pull request" | event-driven — leave cadence as `None`, note in goal |

### Similarity Detection

For `repeated_prompt`, use a simple token-overlap approach (stdlib-only, no sklearn):

1. Tokenize each user message: lowercase, split on whitespace, strip punctuation
2. Remove stop words (a, the, is, of, to, etc.) and tokens < 3 chars
3. Jaccard similarity: `|A ∩ B| / |A ∪ B|`
4. Group messages with similarity ≥ 0.7 across ≥ 3 distinct sessions
5. Use the most recent message as `sample_prompt`

### Transcript Reading

Reuse the same transcript format as efficiency-audit: `~/.claude/projects/<project>/<session>.jsonl`. Filter noise using the same `_is_noise()` patterns from efficiency-audit's scanner. The `--project` flag restricts to one project; omit to scan all projects.

## SKILL.md Changes

Add this section before the existing "## Phase 1: Readiness Gate":

```markdown
## Discovery Entry Path (Phase 2)

Triggered by: "discover loops," "what can I automate," "find loop candidates," "what should I turn into a loop," "any tasks I could hand off to a loop."

### Step 1: Scan

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
echo '{"days":30,"project":"<current-project>"}' | python3 -c "
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

3. Deploy Verification (score 4.5)
   Found deploy-check pattern in 3 sessions.
   Sample: "is the deploy done yet"

Pick a number, or say "from scratch" to design your own, or "show more."
```

### Step 3: Pre-populate Phase 1

When user picks a candidate, replace Q1-Q6 with confirmation variants using the candidate's hints. If a hint is `None`, ask the original question instead.
```

## Interview Pre-population

When a candidate is selected, Phase 1 changes from open-ended questions to confirmations:

| Q | Original (blank slate) | Discovery mode (candidate selected) |
|---|----------------------|-----------------------------------|
| Q1 | "What task should this loop do?" | "I found you {sample_prompt} across {N} sessions. Create a '{goal}' loop?" |
| Q2 | "How often should this run?" | If `cadence_hint` set: "I see a {cadence_hint} pattern. Keep that?" If None: ask original Q2 |
| Q3 | "How would you verify?" | If `verify_hint` set: "You typically verify by {verify_hint}. Use that?" If None: ask original Q3 |
| Q4 | "What needs access to?" | "You access {context_hint}. Anything else?" If None: ask original Q4 |
| Q5 | "When should it stop?" | "You usually stop after one check. Escalate on failure?" (default for polling; adjust per signal type) |
| Q6 | "Worst case if wrong?" | "{risk_hint}. Any risk I'm missing?" If None: ask original Q6 |

Phases 2 and 3 (Q7-Q11) remain unchanged and asked fresh — discovery data doesn't cover per-iteration details.

## Minimal Viable Implementation

For v1 of Phase 2:

- **In scope:** `repeated_prompt` and `temporal_cue` signals (highest weight, clearest automation value)
- **In scope:** Pre-populated Phase 1 confirmation flow
- **In scope:** 12+ unit tests covering signal detection, scoring, cadence extraction, empty results, and multi-project scanning
- **Out of scope:** `status_check`, `compounding_state`, `manual_verification` signals (add in Phase 2.1)
- **Out of scope:** Cosine similarity for prompt clustering — v1 uses Jaccard similarity (simpler, stdlib)
- **Out of scope:** Cross-project deduplication — each project scanned independently

## Non-Goals (Phase 2)

- Does NOT auto-create loops without user confirmation — discovery presents candidates, user chooses
- Does NOT modify any transcript files — read-only scan
- Does NOT require new dependencies — stdlib-only Python (math, json, re, pathlib, collections)
- Does NOT change the tier detection or output generation logic
- Does NOT execute or schedule discovered loops

## Testing Approach

Following the `writing-skills` TDD methodology:

1. **RED:** Create test transcripts with known repeat patterns, run scanner, verify candidates
2. **GREEN:** Implement scanner logic until tests pass
3. **REFACTOR:** Close loopholes — test with noise-heavy transcripts, single-session projects, empty directories

Scripts tested independently with `unittest`. SKILL.md changes validated by running the full existing test suite (58 tests) to confirm no regression.
