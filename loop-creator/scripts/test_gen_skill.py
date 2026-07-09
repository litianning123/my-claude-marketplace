#!/usr/bin/env python3
"""Tests for gen_skill."""
import unittest
from gen_skill import generate_skill_md, generate_reference_implementation


class GenerateSkillMdTests(unittest.TestCase):
    def setUp(self):
        self.goal = "Automated PR review"
        self.trigger_phrases = "review my PR, check this PR, PR review"
        self.description = "Reviews pull requests for code quality, security, and style issues."
        self.operating_procedure = (
            "1. Read the git diff for the PR.\n"
            "2. Check for common issues: security, style, logic errors.\n"
            "3. Post findings as inline comments.\n"
            "4. Summarize results in a review comment."
        )

    def test_returns_non_empty_string(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_includes_yaml_frontmatter(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIn("---", result)
        self.assertIn("name:", result)
        self.assertIn("description:", result)

    def test_includes_goal_in_title(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIn("PR review", result)

    def test_includes_trigger_phrases_in_description(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIn("review my PR", result)

    def test_includes_operating_procedure(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIn("Read the git diff", result)
        self.assertIn("Post findings as inline comments", result)

    def test_name_is_slugified_goal(self):
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        self.assertIn("name: automated-pr-review", result)

    def test_frontmatter_is_well_formed(self):
        """YAML frontmatter must have start/end delimiters with fields between them."""
        result = generate_skill_md(
            self.goal, self.trigger_phrases,
            self.description, self.operating_procedure,
        )
        lines = result.split("\n")
        # First line must be ---
        self.assertEqual(lines[0], "---")
        # Must have a closing --- before body
        dashes = [i for i, line in enumerate(lines) if line == "---"]
        self.assertGreaterEqual(len(dashes), 2)

    def test_uses_fallback_description_when_empty(self):
        result = generate_skill_md(
            "Monitor CI", "", "", "Check CI status."
        )
        self.assertIn("name:", result.lower())
        self.assertIn("description:", result.lower())
        self.assertIn("Check CI status", result)


class GenerateReferenceImplementationTests(unittest.TestCase):
    def setUp(self):
        self.goal = "Daily project review"
        self.scope = "Inspect workspace, write report, do not modify source files"
        self.expected_output = "outputs/daily-review.md"
        self.action = "Inspect the workspace and write a daily review report"
        self.verify = "- outputs/daily-review.md exists\n- All sections present\n- PROGRESS.md updated"
        self.safety = "- Do not delete files\n- Do not modify source files\n- Only write to outputs/ and PROGRESS.md"
        self.cadence = "24h"
        self.stop = "Stop after writing report. Escalate to human review if same blocker appears twice."
        self.initial_status = "Manual setup -- validate before scheduling"
        self.output_name = "daily-review.md"

    def test_returns_dict(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        self.assertIsInstance(result, dict)

    def test_returns_non_empty_dict(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        self.assertTrue(len(result) > 0)

    def test_all_keys_have_reference_implementation_prefix(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        for key in result:
            self.assertTrue(
                key.startswith("reference-implementation/"),
                f"Key '{key}' does not start with 'reference-implementation/'",
            )

    def test_includes_standard_project_files(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        self.assertIn("reference-implementation/TASK.md", result)
        self.assertIn("reference-implementation/LOOP_INSTRUCTIONS.md", result)
        self.assertIn("reference-implementation/PROGRESS.md", result)

    def test_includes_output_file(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        self.assertIn("reference-implementation/outputs/daily-review.md", result)

    def test_all_files_are_non_empty(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        for name, content in result.items():
            self.assertTrue(
                len(content) > 0,
                f"File '{name}' is empty",
            )

    def test_task_md_references_goal(self):
        result = generate_reference_implementation(
            self.goal, self.scope, self.expected_output,
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            self.output_name,
        )
        self.assertIn("Daily project review", result["reference-implementation/TASK.md"])

    def test_output_file_uses_provided_name(self):
        """When output_name is custom, the output key reflects it."""
        result = generate_reference_implementation(
            self.goal, self.scope, "outputs/ci-report.md",
            self.action, self.verify, self.safety,
            self.cadence, self.stop, self.initial_status,
            "ci-report.md",
        )
        self.assertIn("reference-implementation/outputs/ci-report.md", result)


if __name__ == "__main__":
    unittest.main()
