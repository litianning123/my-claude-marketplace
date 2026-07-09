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


    def test_all_factors_true_without_reusable_returns_skill(self):
        """Score 5 without reusable → skill (complex, not reusable-labeled)."""
        answers = {
            "multi_step": True,
            "stateful": True,
            "external_tools": True,
            "human_review": True,
            "complex_verification": True,
            "reusable": False,
        }
        tier, reasoning = detect_tier(answers)
        self.assertEqual(tier, "skill")
        self.assertNotIn("reusable", reasoning.lower())

    def test_missing_keys_do_not_crash(self):
        """Missing keys should default gracefully (no crash)."""
        tier, reasoning = detect_tier({})
        self.assertEqual(tier, "command")
        self.assertIn("no complexity factors", reasoning.lower())

    def test_non_dict_input_returns_command(self):
        """Non-dict input should return command tier gracefully."""
        tier, reasoning = detect_tier(None)
        self.assertEqual(tier, "command")
        self.assertIn("invalid input", reasoning.lower())


if __name__ == "__main__":
    unittest.main()
