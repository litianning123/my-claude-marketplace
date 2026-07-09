# Loop Creator Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a wizard-style Claude Code skill that interviews users about their automation goal and generates ready-to-run loop configurations at three tiers (command, project folder, reusable skill).

**Architecture:** SKILL.md orchestrates a three-phase interview (readiness gate → scope → cadence), then delegates to stdlib-only Python scripts that return generated content as strings. The agent controls all filesystem side effects. Scripts are independently testable with `unittest`.

**Tech Stack:** Python 3 (stdlib only — `argparse`, `unittest`, `json`, `pathlib`), Markdown/YAML frontmatter for SKILL.md, JSON for plugin manifest.

## Global Constraints

- Scripts return content as strings — they NEVER write files directly (agent controls all writes)
- All Python scripts use stdlib only — no pip dependencies
- Tests use `unittest` (not pytest) — run from `scripts/` directory: `python3 -m unittest test_*.py`
- SKILL.md follows `writing-skills` conventions: YAML frontmatter, "Use when..." description, no workflow summaries in description
- The "manual before scheduled" hard constraint must appear in ALL tier outputs
- Tier detection is heuristic + confirmation — never auto-select tier without asking

---

### Task 1: Plugin Scaffold

**Files:**
- Create: `loop-creator/.claude-plugin/plugin.json`
- Create: `loop-creator/README.md`

**Interfaces:**
- Produces: `plugin.json` with `name: "loop-creator"` — no consumers depend on this

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p loop-creator/.claude-plugin loop-creator/skills/loop-creator loop-creator/scripts
```

- [ ] **Step 2: Write plugin.json**

Create `loop-creator/.claude-plugin/plugin.json`:

```json
{
  "name": "loop-creator",
  "description": "Wizard-style skill that interviews users about their automation goal and generates ready-to-run Claude Code loop configurations — from simple /loop commands to full project folders to reusable skills. Encodes loop engineering best practices: readiness check, permission ladder, maker-checker verification, and manual-before-scheduled discipline."
}
```

- [ ] **Step 3: Write README.md skeleton**

Create `loop-creator/README.md`:

```markdown
# Loop Creator

A Claude Code plugin that helps you design and generate loop configurations through a guided interview. 

## What it does

- Interviews you about your automation goal (what repeats? how do you verify? when should it stop?)
- Recommends the right output format (command, project folder, or reusable skill)
- Generates ready-to-use loop configurations with safety boundaries, verification checklists, and scheduling instructions

## Installation

Copy the `loop-creator/` directory into your Claude Code plugins directory.

## Usage

Invoke with phrases like:
- "Create a loop for my daily standup"
- "Set up a CI monitoring loop"
- "I want to automate my weekly code review"

The wizard will guide you through readiness check, scope definition, and scheduling — then generate the right files for your needs.

## Output Tiers

| Tier | What you get | Best for |
|------|-------------|----------|
| Command | A ready-to-paste `/loop` command | Simple polling, stateless checks |
| Project | A complete loop workspace (TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, outputs/) | Stateful, multi-step workflows |
| Skill | A reusable SKILL.md + reference implementation | Team workflows, recurring patterns |
```

- [ ] **Step 4: Commit**

```bash
git add loop-creator/.claude-plugin/plugin.json loop-creator/README.md
git commit -m "feat: add loop-creator plugin scaffold

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Tier Detector

**Files:**
- Create: `loop-creator/scripts/tier_detector.py`
- Create: `loop-creator/scripts/test_tier_detector.py`

**Interfaces:**
- Consumes: (none — first logic module)
- Produces: `detect_tier(answers: dict) -> tuple[str, str]` — takes interview answers dict, returns `(tier_name, reasoning_string)`. Tier names: `"command"`, `"project"`, `"skill"`.

- [ ] **Step 1: Write the failing tests**

Create `loop-creator/scripts/test_tier_detector.py`:

```python
#!/usr/bin/env python3
"""Tests for tier_detector."""
import unittest
from tier_detector import detect_tier


class DetectTierTests(unittest.TestCase):
    def test_simple_stateless_returns_command(self):
        """Single-step, stateless, read-only → command tier."""
        answers = {
            "repeats": "every 30 minutes",
            "verify": "check if CI is green or red",
            "context": "CI logs",
            "stop": "notify me and stop",
            "risk": "no risk, read-only",
            "multi_step": False,
            "stateful": False,
            "external_tools": False,
            "human_review": False,
            "complex_verification": False,
            "reusable": False,
        }
        tier, reasoning = detect_tier(answers)
        self.assertEqual(tier, "command")
        self.assertIn("single run", reasoning.lower())

    def test_stateful_multi_step_returns_project(self):
        """Multi-step, stateful, needs file persistence → project tier."""
        answers = {
            "repeats": "daily",
            "verify": "checklist of required sections",
            "context": "project folder and git log",
            "stop": "after writing report and updating state",
            "risk": "low, writes only to outputs folder",
            "multi_step": True,
            "stateful": True,
            "external_tools": False,
            "human_review": True,
            "complex_verification": True,
            "reusable": False,
        }
        tier, reasoning = detect_tier(answers)
        self.assertEqual(tier, "project")
        self.assertIn("state", reasoning.lower())

    def test_reusable_returns_skill(self):
        """Reusable across projects → skill tier."""
        answers = {
            "repeats": "per pull request",
            "verify": "test suite passes",
            "context": "git diff, test output",
            "stop": "after review posted or tests pass",
            "risk": "medium, creates PR comments",
            "multi_step": True,
            "stateful": False,
            "external_tools": True,
            "human_review": True,
            "complex_verification": True,
            "reusable": True,
        }
        tier, reasoning = detect_tier(answers)
        self.assertEqual(tier, "skill")
        self.assertIn("reusable", reasoning.lower())

    def test_barely_project_threshold(self):
        """Score 3 → project tier (just above command cutoff of 2)."""
        answers = {
            "multi_step": True,      # +1
            "stateful": True,         # +1
            "external_tools": True,   # +1
            "human_review": False,
            "complex_verification": False,
            "reusable": False,
        }
        tier, _ = detect_tier(answers)
        self.assertEqual(tier, "project")

    def test_reusable_trumps_score(self):
        """Reusable flag alone pushes to skill even with low score."""
        answers = {
            "multi_step": False,
            "stateful": False,
            "external_tools": False,
            "human_review": False,
            "complex_verification": False,
            "reusable": True,  # +2
        }
        tier, _ = detect_tier(answers)
        self.assertEqual(tier, "skill")

    def test_empty_answers_defaults_to_command(self):
        """All false/empty → command tier."""
        answers = {
            "multi_step": False,
            "stateful": False,
            "external_tools": False,
            "human_review": False,
            "complex_verification": False,
            "reusable": False,
        }
        tier, _ = detect_tier(answers)
        self.assertEqual(tier, "command")

    def test_reasoning_mentions_key_factors(self):
        """Reasoning string includes the factors that drove the decision."""
        answers = {
            "multi_step": True,
            "stateful": True,
            "external_tools": False,
            "human_review": True,
            "complex_verification": False,
            "reusable": False,
        }
        _, reasoning = detect_tier(answers)
        self.assertIn("multi-step", reasoning.lower())
        self.assertIn("stateful", reasoning.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_tier_detector.py -v 2>&1
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tier_detector'`

- [ ] **Step 3: Write minimal implementation**

Create `loop-creator/scripts/tier_detector.py`:

```python
#!/usr/bin/env python3
"""
Tier detector — scores interview answers to recommend output tier.

Returns (tier_name, reasoning_string) where tier_name is one of:
"command", "project", "skill".
"""


def detect_tier(answers: dict) -> tuple[str, str]:
    """
    Score interview answers and return (tier, reasoning).

    Scoring:
        +1 each: multi_step, stateful, external_tools,
                 human_review, complex_verification
        +2: reusable ("I want to reuse this" / "my team needs this")

    Thresholds:
        score <= 2  → "command"  (simple, stateless, single-run)
        score <= 4  → "project"  (stateful, multi-step, needs files)
        score >  4  → "skill"    (reusable, complex, team-facing)
    """
    score = 0
    factors = []

    checks = [
        ("multi_step", "multi-step workflow"),
        ("stateful", "stateful (needs persistence between runs)"),
        ("external_tools", "uses external tools/connectors"),
        ("human_review", "requires human review gate"),
        ("complex_verification", "complex verification (tests, schema, multi-check)"),
    ]

    for key, label in checks:
        if answers.get(key):
            score += 1
            factors.append(label)

    if answers.get("reusable"):
        score += 2
        factors.append("marked as reusable across projects/teams")

    if score <= 2:
        tier = "command"
        tier_label = "a simple /loop command"
    elif score <= 4:
        tier = "project"
        tier_label = "a project folder with TASK.md, LOOP_INSTRUCTIONS.md, and PROGRESS.md"
    else:
        tier = "project"
        tier_label = "a project folder with TASK.md, LOOP_INSTRUCTIONS.md, and PROGRESS.md"
        if answers.get("reusable"):
            tier = "skill"
            tier_label = "a reusable SKILL.md + reference implementation"

    reasoning = _build_reasoning(tier_label, score, factors)
    return tier, reasoning


def _build_reasoning(tier_label: str, score: int, factors: list[str]) -> str:
    """Build a human-readable reasoning string."""
    factor_text = ", ".join(factors) if factors else "no complexity factors detected"
    return (
        f"Score {score} — {factor_text}. "
        f"Recommended: {tier_label}."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_tier_detector.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop-creator/scripts/tier_detector.py loop-creator/scripts/test_tier_detector.py
git commit -m "feat: add tier detector with heuristic scoring

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Command Generator (Tier 1)

**Files:**
- Create: `loop-creator/scripts/gen_command.py`
- Create: `loop-creator/scripts/test_gen_command.py`

**Interfaces:**
- Consumes: (none — independent generator)
- Produces: `generate_command(goal: str, cadence: str, context: str, action: str, stop_condition: str, verify: str, risk: str) -> str` — returns a ready-to-paste `/loop` command string

- [ ] **Step 1: Write the failing tests**

Create `loop-creator/scripts/test_gen_command.py`:

```python
#!/usr/bin/env python3
"""Tests for gen_command."""
import unittest
from gen_command import generate_command, generate_manual_test_reminder


class GenerateCommandTests(unittest.TestCase):
    def setUp(self):
        self.goal = "Monitor CI status for PR #123"
        self.cadence = "30m"
        self.context = "CI run logs from the latest commit"
        self.action = "classify the result as passing, failing, or in-progress"
        self.stop = "notify me and stop after one check"
        self.verify = "check that the CI status was correctly read from the logs"
        self.risk = "read-only, no code modification"

    def test_returns_non_empty_string(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_includes_loop_prefix(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIn("/loop", result)

    def test_includes_cadence(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIn("30m", result)

    def test_includes_goal_in_prompt(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIn("CI status", result)

    def test_includes_safety_boundary(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIn("Do not modify", result)

    def test_read_only_risk_adds_safety_note(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify,
            risk="read-only"
        )
        self.assertIn("Do not modify any code", result)

    def test_medium_risk_adds_human_review_note(self):
        result = generate_command(
            self.goal, self.cadence, self.context,
            self.action, self.stop, self.verify,
            risk="could create PR comments, no code changes"
        )
        self.assertIn("human review", result.lower())

    def test_short_cadence_uses_polling_language(self):
        result = generate_command(
            self.goal, "5m", self.context,
            self.action, self.stop, self.verify, self.risk
        )
        self.assertIn("poll", result.lower())


class GenerateManualTestReminderTests(unittest.TestCase):
    def test_returns_reminder_with_steps(self):
        reminder = generate_manual_test_reminder()
        self.assertIn("manually", reminder.lower())
        self.assertIn("schedule", reminder.lower())

    def test_includes_verification_instruction(self):
        reminder = generate_manual_test_reminder()
        self.assertIn("verify", reminder.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_command.py -v 2>&1
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `loop-creator/scripts/gen_command.py`:

```python
#!/usr/bin/env python3
"""
Tier 1 generator — produces a ready-to-paste /loop command.
"""


def generate_command(
    goal: str,
    cadence: str,
    context: str,
    action: str,
    stop_condition: str,
    verify: str,
    risk: str,
) -> str:
    """
    Generate a /loop command string from interview answers.

    Returns a multi-line string ready to paste into Claude Code.
    """
    safety_line = _safety_line(risk)
    cadence_note = _cadence_note(cadence)

    return (
        f"/loop {cadence} {goal}.\n"
        f"\n"
        f"Context: {context}\n"
        f"Action: {action}\n"
        f"Stop when: {stop_condition}\n"
        f"Verify: {verify}\n"
        f"{safety_line}"
        f"{cadence_note}"
    )


def _safety_line(risk: str) -> str:
    """Determine the safety boundary line based on risk level."""
    risk_lower = risk.lower()
    if "read-only" in risk_lower or "no code" in risk_lower:
        return "Do not modify any code or files.\n"
    if "code" in risk_lower or "modif" in risk_lower:
        return "Only modify files explicitly listed above. Mark anything uncertain for human review.\n"
    return "If uncertain whether an action is safe, stop and mark for human review.\n"


def _cadence_note(cadence: str) -> str:
    """Add guidance for short polling intervals."""
    try:
        num = int("".join(c for c in cadence if c.isdigit()))
    except ValueError:
        return ""
    unit = "".join(c for c in cadence if c.isalpha()).lower()
    if unit in ("m", "min", "minute", "minutes") and num <= 30:
        return f"\n(This is a polling interval. The loop checks every {cadence} and reports only when something changed.)\n"
    return ""


def generate_manual_test_reminder() -> str:
    """Generate the mandatory manual-test-before-scheduling reminder."""
    return (
        "## Before scheduling\n"
        "Run this manually once first:\n"
        "1. Paste the command without `/loop <cadence>` into Claude Code\n"
        "2. Verify the output is correct\n"
        "3. Check that no unexpected files were modified\n"
        "4. Only then schedule with the full `/loop` command above\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_command.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop-creator/scripts/gen_command.py loop-creator/scripts/test_gen_command.py
git commit -m "feat: add command generator (tier 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Project Generator (Tier 2)

**Files:**
- Create: `loop-creator/scripts/gen_project.py`
- Create: `loop-creator/scripts/test_gen_project.py`

**Interfaces:**
- Consumes: (none — independent generator)
- Produces:
  - `generate_task_md(goal: str, scope: str, expected_output: str) -> str`
  - `generate_loop_instructions_md(action_steps: str, verify_checklist: str, safety_rules: str, cadence: str, stop_policy: str) -> str`
  - `generate_progress_md(goal: str, initial_status: str) -> str`
  - `generate_output_starter(output_name: str) -> str`
  - `generate_all_project_files(answers: dict) -> dict[str, str]` — returns `{filename: content}` dict

- [ ] **Step 1: Write the failing tests**

Create `loop-creator/scripts/test_gen_project.py`:

```python
#!/usr/bin/env python3
"""Tests for gen_project."""
import unittest
from gen_project import (
    generate_task_md,
    generate_loop_instructions_md,
    generate_progress_md,
    generate_output_starter,
    generate_all_project_files,
)


class GenerateTaskMdTests(unittest.TestCase):
    def test_includes_goal(self):
        result = generate_task_md(
            goal="Daily project review",
            scope="Read project folder, write reports",
            expected_output="outputs/daily-review.md, PROGRESS.md",
        )
        self.assertIn("Daily project review", result)
        self.assertIn("# Daily Project Review Loop", result)

    def test_includes_scope_boundaries(self):
        result = generate_task_md(
            goal="Daily project review",
            scope="Inspect workspace, do not modify source files",
            expected_output="outputs/daily-review.md",
        )
        self.assertIn("not modify source files", result.lower())

    def test_includes_expected_output(self):
        result = generate_task_md(
            goal="CI monitor",
            scope="Read CI logs",
            expected_output="outputs/ci-status.md",
        )
        self.assertIn("outputs/ci-status.md", result)

    def test_safe_scope_defaults_applied(self):
        """When scope doesn't mention safety, defaults are added."""
        result = generate_task_md(
            goal="Test loop",
            scope="Read files",
            expected_output="report.md",
        )
        self.assertIn("should not modify", result.lower())


class GenerateLoopInstructionsMdTests(unittest.TestCase):
    def setUp(self):
        self.action = "Inspect workspace, write daily review to outputs/daily-review.md"
        self.verify = "- outputs/daily-review.md exists\n- All sections present"
        self.safety = "- Do not delete files\n- Do not modify source files"
        self.cadence = "24h"
        self.stop = "Stop after writing report. Escalate if same blocker appears twice."

    def test_includes_action_steps(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, self.cadence, self.stop
        )
        self.assertIn("Inspect workspace", result)

    def test_includes_verification_checklist(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, self.cadence, self.stop
        )
        self.assertIn("Verification Checklist", result)
        self.assertIn("outputs/daily-review.md exists", result)

    def test_includes_safety_rules(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, self.cadence, self.stop
        )
        self.assertIn("Safety Rules", result)
        self.assertIn("Do not delete files", result)

    def test_includes_scheduled_run_policy(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, self.cadence, self.stop
        )
        self.assertIn("Scheduled Run Policy", result)

    def test_includes_failure_policy(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, self.cadence, self.stop
        )
        self.assertIn("Failure Policy", result)

    def test_short_cadence_includes_testing_advice(self):
        result = generate_loop_instructions_md(
            self.action, self.verify, self.safety, "15m", self.stop
        )
        self.assertIn("testing interval", result.lower())


class GenerateProgressMdTests(unittest.TestCase):
    def test_includes_goal(self):
        result = generate_progress_md(
            goal="Daily project review",
            initial_status="Manual setup phase",
        )
        self.assertIn("Daily project review", result)

    def test_includes_initial_status(self):
        result = generate_progress_md(
            goal="CI monitor",
            initial_status="Awaiting first manual run",
        )
        self.assertIn("Awaiting first manual run", result)

    def test_includes_standard_sections(self):
        result = generate_progress_md("Test loop", "Active")
        for section in ["Current State", "Last Run", "Open Items",
                        "Blockers", "Needs Human Review",
                        "Next Run Should", "Decisions Made", "Do Not Repeat"]:
            self.assertIn(section, result)

    def test_do_not_repeat_defaults(self):
        result = generate_progress_md("Test", "Active")
        self.assertIn("Do not modify source files", result)


class GenerateOutputStarterTests(unittest.TestCase):
    def test_returns_placeholder(self):
        result = generate_output_starter("daily-review.md")
        self.assertIn("daily-review.md", result.lower() if result else "")
        self.assertIn("No loop run", result)


class GenerateAllProjectFilesTests(unittest.TestCase):
    def setUp(self):
        self.answers = {
            "goal": "Daily project review",
            "scope": "Inspect workspace, write report, do not modify source files",
            "expected_output": "outputs/daily-review.md",
            "action": "Inspect the workspace and write a daily review report",
            "verify": "- outputs/daily-review.md exists\n- All sections present\n- PROGRESS.md updated",
            "safety": "- Do not delete files\n- Do not modify source files\n- Only write to outputs/ and PROGRESS.md",
            "cadence": "24h",
            "stop": "Stop after writing report. Escalate to human review if same blocker appears twice.",
            "initial_status": "Manual setup — validate before scheduling",
            "output_name": "daily-review.md",
        }

    def test_returns_dict_with_all_files(self):
        result = generate_all_project_files(self.answers)
        self.assertIn("TASK.md", result)
        self.assertIn("LOOP_INSTRUCTIONS.md", result)
        self.assertIn("PROGRESS.md", result)
        self.assertIn("outputs/daily-review.md", result)

    def test_all_files_non_empty(self):
        result = generate_all_project_files(self.answers)
        for name, content in result.items():
            self.assertTrue(len(content) > 0, f"{name} is empty")

    def test_task_md_references_output(self):
        result = generate_all_project_files(self.answers)
        self.assertIn("daily-review.md", result["TASK.md"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_project.py -v 2>&1
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `loop-creator/scripts/gen_project.py`:

```python
#!/usr/bin/env python3
"""
Tier 2 generator — produces a complete loop project folder.

Generates: TASK.md, LOOP_INSTRUCTIONS.md, PROGRESS.md, outputs/<name>.md
Following the article's templates from Sections 3-4.
"""

from textwrap import dedent


def generate_task_md(goal: str, scope: str, expected_output: str) -> str:
    """Generate TASK.md content."""
    safe_scope = scope
    if "not modify" not in safe_scope.lower() and "should not" not in safe_scope.lower():
        safe_scope += (
            "\nClaude should not modify source files, delete files, rename files, "
            "move files, send messages, open tickets, or interact with external "
            "systems during this first version of the loop."
        )

    return dedent(f"""\
    # {goal.title()} Loop

    ## Goal
    {goal}

    ## Expected Output
    Each run should produce or update:
    {expected_output}

    ## Scope
    {safe_scope}
    """)


def generate_loop_instructions_md(
    action_steps: str,
    verify_checklist: str,
    safety_rules: str,
    cadence: str,
    stop_policy: str,
) -> str:
    """Generate LOOP_INSTRUCTIONS.md content."""
    cadence_section = _cadence_section(cadence)

    return dedent(f"""\
    # Loop Instructions

    You are running a {cadence} loop.

    ## Before You Start
    1. Read `TASK.md`.
    2. Read `PROGRESS.md`.
    3. Inspect the relevant context for this run.
    4. Identify what changed, what is incomplete, and what needs human review.

    ## What You Should Do
    {action_steps}

    After completing the action, update `PROGRESS.md` with:
    - Date of this run
    - Summary of what happened
    - Files or areas checked
    - Output produced
    - What the next run should do
    - Anything that needs human review

    ## Safety Rules
    {safety_rules}
    - If you are unsure whether an action is allowed, stop and ask for human review.

    {cadence_section}

    ## Verification Checklist
    Before ending the run, verify the following:
    {verify_checklist}

    ### Safety Boundary
    Only the files explicitly listed above may be modified.
    If any other file was modified, stop and report the issue.

    ## Failure Policy
    If verification fails:
    1. If the failure is a missing section or output, fix it once.
    2. If `PROGRESS.md` was not updated, update it once.
    3. If any forbidden file was modified, stop immediately and report the issue.
    4. If the same verification check fails twice, stop and mark the run as needing human review.

    ## Stop Policy
    {stop_policy}
    """)


def _cadence_section(cadence: str) -> str:
    """Build the scheduled run policy section."""
    try:
        num = int("".join(c for c in cadence if c.isdigit()))
    except ValueError:
        num = 0
    unit = "".join(c for c in cadence if c.isalpha()).lower()

    is_testing = unit in ("m", "min", "minute", "minutes") and num <= 30

    testing_note = ""
    if is_testing:
        testing_note = (
            "\n**Note:** This is a short testing interval. "
            "Use it only to validate behavior. Move to the real cadence "
            "once the loop is stable.\n"
        )

    return dedent(f"""\
    ## Scheduled Run Policy
    When this loop runs on a schedule:{testing_note}
    - If there are meaningful changes, write a concise report.
    - If there are no meaningful changes, write a short "No meaningful changes" note.
    - If human review is needed, mark it clearly in `PROGRESS.md`.
    - If the same blocker appears in two consecutive runs, do not keep retrying. Escalate to human review.
    - If verification fails twice, stop and mark the run as not accepted.
    - Keep scheduled outputs short unless there is something important to report.
    - Do not create extra files unless explicitly allowed.
    """)


def generate_progress_md(goal: str, initial_status: str) -> str:
    """Generate PROGRESS.md content with starter template."""
    return dedent(f"""\
    # Loop Progress

    ## Current State
    - Status: {initial_status}
    - Main objective: {goal}
    - Current focus: Validate the loop manually before scheduling
    - Last updated:

    ## Last Run
    - Date:
    - Trigger:
    - Summary:
    - Files reviewed:
    - Output produced:

    ## Open Items
    -

    ## Blockers
    -

    ## Needs Human Review
    -

    ## Next Run Should
    - Read `TASK.md`, `PROGRESS.md`, and `LOOP_INSTRUCTIONS.md`.
    - Inspect the workspace.
    - Produce the expected output.
    - Update this file before stopping.

    ## Decisions Made
    - The loop starts with local file access only.
    - Scheduling should happen only after stable manual runs.

    ## Do Not Repeat
    - Do not modify source files.
    - Do not delete, rename, or move files.
    - Do not create extra files unless explicitly instructed.
    """)


def generate_output_starter(output_name: str) -> str:
    """Generate a starter output file."""
    base = output_name.replace(".md", "").replace("outputs/", "").replace("-", " ").title()
    return f"# {base}\n\nNo loop run has been completed yet.\n"


def generate_all_project_files(answers: dict) -> dict[str, str]:
    """Generate all project files from interview answers.

    Args:
        answers: dict with keys: goal, scope, expected_output, action,
                 verify, safety, cadence, stop, initial_status, output_name

    Returns:
        dict mapping filename -> content
    """
    goal = answers.get("goal", "Loop Task")
    scope = answers.get("scope", "Read and report only.")
    expected_output = answers.get("expected_output", "outputs/report.md")
    action = answers.get("action", "Inspect the workspace and produce output.")
    verify = answers.get("verify", "- Output file exists\n- Required sections present")
    safety = answers.get("safety", "- Do not delete files\n- Do not modify source files")
    cadence = answers.get("cadence", "24h")
    stop = answers.get("stop", "Stop after completing the action. Escalate if blocked.")
    initial_status = answers.get("initial_status", "Manual setup — validate before scheduling")
    output_name = answers.get("output_name", "report.md")

    return {
        "TASK.md": generate_task_md(goal, scope, expected_output),
        "LOOP_INSTRUCTIONS.md": generate_loop_instructions_md(
            action, verify, safety, cadence, stop
        ),
        "PROGRESS.md": generate_progress_md(goal, initial_status),
        f"outputs/{output_name}": generate_output_starter(output_name),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_project.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop-creator/scripts/gen_project.py loop-creator/scripts/test_gen_project.py
git commit -m "feat: add project generator (tier 2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Skill Generator (Tier 3)

**Files:**
- Create: `loop-creator/scripts/gen_skill.py`
- Create: `loop-creator/scripts/test_gen_skill.py`

**Interfaces:**
- Consumes: `gen_project.generate_all_project_files` — reused to generate the reference implementation
- Produces: `generate_skill_md(goal: str, trigger_phrases: str, description: str, operating_procedure: str) -> str` — returns a complete SKILL.md string

- [ ] **Step 1: Write the failing tests**

Create `loop-creator/scripts/test_gen_skill.py`:

```python
#!/usr/bin/env python3
"""Tests for gen_skill."""
import unittest
from gen_skill import generate_skill_md, generate_reference_implementation


class GenerateSkillMdTests(unittest.TestCase):
    def setUp(self):
        self.goal = "Daily project review"
        self.triggers = "daily review, project review, morning check"
        self.description = "Use when the user wants a recurring daily project review"
        self.procedure = (
            "1. Read TASK.md and PROGRESS.md\n"
            "2. Inspect the workspace\n"
            "3. Write outputs/daily-review.md\n"
            "4. Update PROGRESS.md"
        )

    def test_has_yaml_frontmatter(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("---", result)
        self.assertIn("name:", result)
        self.assertIn("description:", result)

    def test_name_is_kebab_case(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("name: daily-project-review", result.lower().replace(" ", "-"))

    def test_description_starts_with_use_when(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("Use when", result)

    def test_includes_procedure(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("Read TASK.md", result)

    def test_includes_file_structure_section(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("File Structure", result)

    def test_includes_common_mistakes(self):
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertIn("Common Mistakes", result)

    def test_no_placeholders_in_output(self):
        """Generated skill should not contain TBD or TODO."""
        result = generate_skill_md(
            self.goal, self.triggers, self.description, self.procedure
        )
        self.assertNotIn("TBD", result)
        self.assertNotIn("TODO", result)


class GenerateReferenceImplementationTests(unittest.TestCase):
    def test_returns_dict_with_ref_dir(self):
        result = generate_reference_implementation(
            goal="CI monitor",
            scope="Read CI logs",
            expected_output="outputs/ci-status.md",
            action="Check CI status",
            verify="- ci-status.md exists",
            safety="- Do not modify code",
            cadence="30m",
            stop="Stop after reporting",
            initial_status="Reference",
            output_name="ci-status.md",
        )
        self.assertIn("reference-implementation/TASK.md", result)
        self.assertIn("reference-implementation/LOOP_INSTRUCTIONS.md", result)
        self.assertIn("reference-implementation/PROGRESS.md", result)

    def test_ref_files_are_non_empty(self):
        result = generate_reference_implementation(
            goal="Test", scope="Read", expected_output="out.md",
            action="Act", verify="Check", safety="Safe",
            cadence="1h", stop="Stop", initial_status="Ref",
            output_name="out.md",
        )
        for name, content in result.items():
            self.assertTrue(len(content) > 0, f"{name} is empty")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_skill.py -v 2>&1
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `loop-creator/scripts/gen_skill.py`:

```python
#!/usr/bin/env python3
"""
Tier 3 generator — produces a reusable SKILL.md + reference implementation.
"""
import re
from textwrap import dedent
from gen_project import generate_all_project_files


def generate_skill_md(
    goal: str,
    trigger_phrases: str,
    description: str,
    operating_procedure: str,
) -> str:
    """Generate a complete SKILL.md string.

    Args:
        goal: The loop's purpose (used to derive the skill name)
        trigger_phrases: Comma-separated phrases that should trigger this skill
        description: The "Use when..." description for the frontmatter
        operating_procedure: Step-by-step procedure the agent follows
    """
    name = _derive_skill_name(goal)
    triggers = trigger_phrases or goal.lower()

    return dedent(f"""\
    ---
    name: {name}
    description: "Use when {description}. Trigger phrases: {triggers}."
    ---

    # {goal.title()}

    ## Overview
    A repeatable loop for: {goal}.

    ## When to Use
    - When the user asks for: {triggers}
    - When the task repeats on a schedule
    - When the output can be verified against a checklist

    ## File Structure
    Create this workspace before the first run:

    ```
    <loop-name>/
    ├── TASK.md
    ├── LOOP_INSTRUCTIONS.md
    ├── PROGRESS.md
    └── outputs/
        └── <output-file>.md
    ```

    Templates for each file are in the reference implementation.

    ## Operating Procedure
    {operating_procedure}

    ## Verification Checklist
    Before ending the run, verify:
    - Output file exists
    - All required sections are present
    - PROGRESS.md was updated
    - No files outside allowed paths were modified

    ## Safety Rules
    - Do not delete, rename, or move files
    - Do not modify source files
    - Only write to the explicitly allowed output paths
    - Mark anything uncertain for human review

    ## Manual Before Scheduled
    Run the loop manually 3-5 times before scheduling. Check:
    - Output is useful and concise
    - State file is updated correctly
    - Safety boundaries are respected
    - Verification passes consistently

    ## Scheduling
    Once manual runs are stable:
    ```
    /loop <cadence> Run the {goal} loop. Follow LOOP_INSTRUCTIONS.md exactly.
    ```

    ## Common Mistakes
    - Scheduling before manual testing
    - Skipping state file update at end of run
    - Letting output grow too verbose
    - Forgetting to check verification before marking done
    - Treating first successful run as proof of reliability

    ## Reference
    See `reference-implementation/` for a complete working example.
    """)


def _derive_skill_name(goal: str) -> str:
    """Derive a kebab-case skill name from the goal string."""
    name = goal.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def generate_reference_implementation(
    goal: str,
    scope: str,
    expected_output: str,
    action: str,
    verify: str,
    safety: str,
    cadence: str,
    stop: str,
    initial_status: str,
    output_name: str,
) -> dict[str, str]:
    """Generate a reference implementation project folder.

    Delegates to gen_project.generate_all_project_files and prefixes
    paths with 'reference-implementation/'.
    """
    answers = {
        "goal": goal,
        "scope": scope,
        "expected_output": expected_output,
        "action": action,
        "verify": verify,
        "safety": safety,
        "cadence": cadence,
        "stop": stop,
        "initial_status": initial_status,
        "output_name": output_name,
    }
    files = generate_all_project_files(answers)
    return {f"reference-implementation/{k}": v for k, v in files.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd loop-creator/scripts && python3 -m unittest test_gen_skill.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop-creator/scripts/gen_skill.py loop-creator/scripts/test_gen_skill.py
git commit -m "feat: add skill generator (tier 3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: SKILL.md — Wizard Orchestrator

**Files:**
- Create: `loop-creator/skills/loop-creator/SKILL.md`

**Interfaces:**
- Consumes: `tier_detector.detect_tier`, `gen_command.generate_command` + `generate_manual_test_reminder`, `gen_project.generate_all_project_files`, `gen_skill.generate_skill_md` + `generate_reference_implementation`
- Produces: The agent-facing skill that drives the interview, delegates to scripts, and writes output files

- [ ] **Step 1: Write SKILL.md**

Create `loop-creator/skills/loop-creator/SKILL.md`:

```markdown
---
name: loop-creator
description: "Use when the user wants to create a Claude Code loop, set up recurring automation, schedule a repeated task, build a /loop command, create a polling workflow, or design any agentic loop. Trigger phrases: 'create a loop', 'set up a loop', 'build a loop', 'automate this to run', 'schedule this task', 'make this recurring', 'I want a loop for', 'design a loop', '/loop creator'."
---

# Loop Creator

A wizard that interviews users about their automation goal and generates ready-to-run Claude Code loop configurations.

## Core Principle

**A loop is not just a repeated prompt. It needs: trigger, context, action, verification, state update, and decision.** This wizard encodes loop engineering best practices — readiness check, permission ladder, maker-checker verification, and manual-before-scheduled discipline.

## Flow

1. Interview user (three phases, one question at a time)
2. Run tier detector script to score answers
3. Present tier recommendation with reasoning — wait for user confirmation
4. Generate output using the matching generator script
5. Write files (for tiers 2-3) or present command (for tier 1)
6. ALWAYS include manual test instructions before scheduling advice

---

## Phase 1: Readiness Gate

Ask one question at a time. If any answer is too vague, push back with a suggestion to narrow scope. The goal is to filter out "bad first loops" early.

### Q1: "What task should this loop do? Describe it in one sentence."

Wait for answer. If the answer is broad ("improve my codebase" / "clean my computer"), push back:
"That's a big scope. A good first loop does one specific, checkable thing. Can we narrow this to one concrete action? For example: 'review the project folder and write a daily summary' rather than 'improve the codebase.'"

### Q2: "How often should this run? (e.g., every 30 minutes, daily, every PR, on file change)"

Wait for answer. Convert to a cadence string for later use (e.g., "every morning" → "24h", "every 30 min" → "30m").

### Q3: "How would you verify the output is correct? What would make you say 'this run was good' vs 'this needs fixing'?"

Wait for answer. If vague ("it should look right"), probe: "Can we make that more concrete? For example: 'the report has all required sections' or 'tests pass' or 'the file exists at the expected path.'"

### Q4: "What does Claude need access to? (e.g., just this folder, git history, GitHub issues, CI logs)"

Wait for answer. This determines context breadth and external tool needs.

### Q5: "When should this loop stop or escalate to you? What's the stop condition?"

Wait for answer. If vague ("when it's done"), push back: "Let's define a concrete stop condition. For example: 'stop after writing the report and updating state' or 'escalate if the same error appears twice.'"

### Q6: "What's the worst that could happen if the loop gets it wrong?"

Wait for answer. Map to permission level:
- "Nothing, it's read-only" → Level 1
- "It could write a bad report" → Level 2
- "It could modify the wrong file" → Level 3
- "It could post something public" → Level 4+

## Phase 2: Scope & Shape

### Q7: "Walk me through one iteration. What should Claude do, step by step?"

Wait for answer. Extract:
- Inputs: what files/APIs/data Claude reads
- Actions: inspect, summarize, classify, draft, fix, notify
- Outputs: where results go

### Q8: "Does each run need to remember what happened in previous runs?"

If yes → stateful, needs PROGRESS.md.
If no → stateless, each run is independent.

### Q9: "Is this just for you, or should others on your team be able to reuse it?"

If team reuse → flag for tier detection (+2 reusable bonus).

## Phase 3: Cadence & Autonomy

### Q10: "What permission level feels right to start?"

Present options derived from Q6 risk answer:
1. Read-only — inspects and reports, changes nothing
2. Draft output — writes reports/plans to an outputs/ folder
3. Sandbox edits — modifies files only in an isolated workspace
4. Human-approved writes — drafts actions, human approves before applying

### Q11: "Should this run on a fixed schedule (every morning), or should it self-pace (check, then decide when to check again)?"

If fixed → cron-based `/loop 24h`
If self-paced → dynamic `/loop` (no interval)

---

## Tier Detection

After all questions, build an answers dict and run the detector:

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from tier_detector import detect_tier

answers = {
    'multi_step': <true|false>,
    'stateful': <true|false>,
    'external_tools': <true|false>,
    'human_review': <true|false>,
    'complex_verification': <true|false>,
    'reusable': <true|false>,
}
tier, reasoning = detect_tier(answers)
print(json.dumps({'tier': tier, 'reasoning': reasoning}))
"
```

Parse the JSON output. Present to user:
"Based on your answers: {reasoning}. I recommend the **{tier}** tier. Sound good?"

Wait for confirmation. If user says no, ask which tier they'd prefer.

---

## Output Generation

### Tier 1: Command

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_command import generate_command, generate_manual_test_reminder

cmd = generate_command(
    goal='<goal>',
    cadence='<cadence>',
    context='<context>',
    action='<action>',
    stop_condition='<stop>',
    verify='<verify>',
    risk='<risk>',
)
print(cmd)
print()
print(generate_manual_test_reminder())
"
```

Present the command and reminder to the user. No files are written.

### Tier 2: Project

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_project import generate_all_project_files

answers = {
    'goal': '<goal>',
    'scope': '<scope>',
    'expected_output': '<expected_output>',
    'action': '<action>',
    'verify': '<verify>',
    'safety': '<safety>',
    'cadence': '<cadence>',
    'stop': '<stop>',
    'initial_status': '<initial_status>',
    'output_name': '<output_name>',
}
files = generate_all_project_files(answers)
print(json.dumps(files))
"
```

Parse the JSON. Ask user where to create the project folder. Write each file using the Write tool.

Then present the manual test prompt:
```
Run the <goal> loop for this workspace.

Follow LOOP_INSTRUCTIONS.md exactly.
Before acting, read TASK.md and PROGRESS.md.
Do not modify any files except the allowed output paths.
```

And the scheduling command:
```
/loop <cadence> Run the <goal> loop. Follow LOOP_INSTRUCTIONS.md exactly.
```

### Tier 3: Skill

First, generate the project files (same as Tier 2) as the reference implementation.

Then generate the SKILL.md:

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
python3 -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_skill import generate_skill_md, generate_reference_implementation

skill = generate_skill_md(
    goal='<goal>',
    trigger_phrases='<triggers>',
    description='<description>',
    operating_procedure='<procedure>',
)
print('===SKILL===')
print(skill)
print('===END_SKILL===')
"
```

Write the SKILL.md and reference implementation files. Tell the user where to place the skill (their skills directory).

---

## Hard Rules

1. **NEVER recommend scheduling without manual test instructions.** Every output must include a "run this manually first" section.
2. **NEVER auto-select a tier.** Always present the reasoning and ask for confirmation.
3. **Push back on vague answers.** If the user's task sounds like a "bad first loop" (vague, high-risk, unverifiable), say so and help them narrow scope.
4. **The permission ladder is non-negotiable.** If a user wants full automation on first loop, recommend starting at Level 1-2 and earning more autonomy.
5. **Scripts are for generation only.** Never use them to write files directly — you (the agent) control all Write operations after user approval.
```

- [ ] **Step 2: Commit**

```bash
git add loop-creator/skills/loop-creator/SKILL.md
git commit -m "feat: add loop-creator SKILL.md wizard orchestrator

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Integration Validation

**Files:**
- Modify: (none — validation only)
- Create: (none — validation only)

**Interfaces:**
- Consumes: all generated scripts and SKILL.md
- Produces: test output confirming all pieces work together

- [ ] **Step 1: Run all unit tests**

```bash
cd loop-creator/scripts && python3 -m unittest discover -v -p "test_*.py"
```

Expected: all tests from tasks 2-5 PASS (27+ tests across 4 test files)

- [ ] **Step 2: Verify plugin structure**

```bash
echo "=== Plugin structure ===" && find loop-creator -type f | sort && echo "" && echo "=== plugin.json valid? ===" && python3 -c "import json; json.load(open('loop-creator/.claude-plugin/plugin.json')); print('YES')" && echo "" && echo "=== SKILL.md has frontmatter? ===" && head -3 loop-creator/skills/loop-creator/SKILL.md
```

Expected:
- All 11 files present (plugin.json, README.md, SKILL.md, 4 scripts, 4 test files)
- `plugin.json valid? YES`
- SKILL.md starts with `---` YAML frontmatter

- [ ] **Step 3: Verify tier detector with sample data**

```bash
cd loop-creator/scripts && python3 -c "
from tier_detector import detect_tier

# Simple CI check → command
tier, reason = detect_tier({
    'multi_step': False, 'stateful': False, 'external_tools': False,
    'human_review': False, 'complex_verification': False, 'reusable': False,
})
assert tier == 'command', f'Expected command, got {tier}'
print(f'Simple CI check → {tier}: {reason}')

# Daily review → project
tier, reason = detect_tier({
    'multi_step': True, 'stateful': True, 'external_tools': False,
    'human_review': True, 'complex_verification': True, 'reusable': False,
})
assert tier == 'project', f'Expected project, got {tier}'
print(f'Daily review → {tier}: {reason}')

# Team PR review → skill
tier, reason = detect_tier({
    'multi_step': True, 'stateful': False, 'external_tools': True,
    'human_review': True, 'complex_verification': True, 'reusable': True,
})
assert tier == 'skill', f'Expected skill, got {tier}'
print(f'Team PR review → {tier}: {reason}')

print('All tier detection scenarios PASSED')
"
```

Expected: All three scenarios print correct tiers and "All tier detection scenarios PASSED"

- [ ] **Step 4: Verify command generation with sample data**

```bash
cd loop-creator/scripts && python3 -c "
from gen_command import generate_command, generate_manual_test_reminder

cmd = generate_command(
    goal='Monitor CI for PR #42',
    cadence='15m',
    context='Latest CI run logs',
    action='Classify result as passing, failing, or in-progress',
    stop_condition='Notify and stop after one check',
    verify='CI status matches actual build result',
    risk='read-only, no code changes',
)
assert '/loop 15m' in cmd
assert 'CI' in cmd
assert 'Do not modify' in cmd
print('Command generation PASSED')
print()
print(cmd)
print()
reminder = generate_manual_test_reminder()
assert 'manually' in reminder.lower()
assert 'schedule' in reminder.lower()
print('Manual test reminder PASSED')
"
```

- [ ] **Step 5: Verify full project generation**

```bash
cd loop-creator/scripts && python3 -c "
from gen_project import generate_all_project_files

answers = {
    'goal': 'Daily project review',
    'scope': 'Inspect workspace, write report only',
    'expected_output': 'outputs/daily-review.md',
    'action': 'Inspect workspace, summarize changes, identify blockers, write daily review',
    'verify': '- outputs/daily-review.md exists\n- Summary section present\n- Blockers section present\n- PROGRESS.md updated',
    'safety': '- Do not delete files\n- Do not modify source files\n- Only write to outputs/ and PROGRESS.md',
    'cadence': '24h',
    'stop': 'Stop after writing report. Escalate if same blocker appears twice.',
    'initial_status': 'Manual setup phase',
    'output_name': 'daily-review.md',
}
files = generate_all_project_files(answers)
assert 'TASK.md' in files
assert 'LOOP_INSTRUCTIONS.md' in files
assert 'PROGRESS.md' in files
assert 'outputs/daily-review.md' in files
assert 'Verification Checklist' in files['LOOP_INSTRUCTIONS.md']
assert 'Safety Rules' in files['LOOP_INSTRUCTIONS.md']
assert 'Failure Policy' in files['LOOP_INSTRUCTIONS.md']
print('Full project generation PASSED')
for name, content in files.items():
    print(f'  {name}: {len(content)} chars')
"
```

- [ ] **Step 6: Verify skill generation**

```bash
cd loop-creator/scripts && python3 -c "
from gen_skill import generate_skill_md, generate_reference_implementation

skill = generate_skill_md(
    goal='Daily project review',
    trigger_phrases='daily review, project check, morning summary',
    description='the user wants a recurring daily review of their project',
    operating_procedure='1. Read TASK.md and PROGRESS.md\n2. Inspect workspace\n3. Write daily review\n4. Update PROGRESS.md',
)
assert '---' in skill
assert 'name: daily-project-review' in skill
assert 'Use when' in skill
assert 'Operating Procedure' in skill
print('Skill generation PASSED')
print(f'  SKILL.md: {len(skill)} chars')

ref = generate_reference_implementation(
    goal='Daily review', scope='Read workspace',
    expected_output='outputs/review.md', action='Inspect and write',
    verify='- review.md exists', safety='- Do not modify source files',
    cadence='24h', stop='Stop after report', initial_status='Reference',
    output_name='review.md',
)
assert len(ref) == 4
assert all(k.startswith('reference-implementation/') for k in ref)
print('Reference implementation PASSED')
for name in ref:
    print(f'  {name}')
"
```

- [ ] **Step 7: Final commit**

```bash
git add -A && git status
```

Verify only loop-creator files are staged, then:

```bash
git commit -m "feat: complete loop-creator plugin with integration validation

All 4 generators + tier detector pass unit tests (27+ tests).
Plugin follows existing repo patterns from efficiency-audit and quicknotes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```
```

- [ ] **Step 8: Self-review the plan against spec**

Check each spec requirement:
- Plugin structure (7 files) → Tasks 1-6 create all files
- Three-phase interview flow → SKILL.md Phase 1-3 sections
- Tier detection with heuristic + confirmation → Task 2 + SKILL.md Tier Detection section
- Three output tiers → Tasks 3, 4, 5 + SKILL.md Output Generation section
- "Manual before scheduled" hard constraint → gen_command reminder, gen_project scheduled policy, gen_skill section, SKILL.md Hard Rules
- Scripts return strings, never write files → confirmed in all gen_*.py implementations
- Stdlib-only Python → no imports beyond stdlib in any script
- unittest for tests → all test files use unittest

No placeholders found. All task steps contain complete code or exact commands.
```

- [ ] **Step 9: Commit the plan**

```bash
git add -f docs/superpowers/plans/2026-07-08-loop-creator.md
git commit -m "docs: add loop-creator implementation plan

Co-Authored-By: Claude <noreply@anthropic.com>"
```
