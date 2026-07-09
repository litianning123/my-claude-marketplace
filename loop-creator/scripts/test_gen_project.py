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
        self.assertIn("daily review", result.lower() if result else "")
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
            "initial_status": "Manual setup -- validate before scheduling",
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
