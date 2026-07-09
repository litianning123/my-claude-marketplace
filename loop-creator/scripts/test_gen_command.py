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
