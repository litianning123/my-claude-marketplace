#!/usr/bin/env python3
"""Tests for hook-doctor."""
import os
import tempfile
import unittest
from pathlib import Path

import sources


class DiscoverSourcesTests(unittest.TestCase):
    def test_returns_empty_list_when_no_configs_exist(self):
        """discover_sources on a temp dir with no .claude should return empty."""
        with tempfile.TemporaryDirectory() as td:
            # Isolate from real user configs by pointing HOME at a clean temp dir
            clean_home = Path(td) / "home"
            clean_home.mkdir()
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(clean_home)
            try:
                result = sources.discover_sources(project_dir=Path(td))
                self.assertEqual(result, [])
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_finds_project_settings_json(self):
        """A project with .claude/settings.json should be discovered."""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            (proj / ".claude").mkdir()
            (proj / ".claude" / "settings.json").write_text("{}")
            result = sources.discover_sources(project_dir=proj)
            paths = [str(s.path) for s in result]
            self.assertIn(str((proj / ".claude" / "settings.json").resolve()), paths)

    def test_finds_plugin_hooks_json(self):
        """hooks.json under a plugins dir should be discovered."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            hooks_dir = base / ".claude" / "plugins" / "my-plugin" / "hooks"
            hooks_dir.mkdir(parents=True)
            (hooks_dir / "hooks.json").write_text("{}")
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                self.assertTrue(
                    any("hooks.json" in str(s.path) for s in result),
                    "Should find hooks.json in plugin tree",
                )
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]

    def test_dedup_by_realpath(self):
        """Symlinked plugin dir should not produce duplicates."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            base_claude_plugins = base / ".claude" / "plugins"
            real_dir = base_claude_plugins / "real-plugin" / "hooks"
            real_dir.mkdir(parents=True)
            (real_dir / "hooks.json").write_text("{}")
            link_dir = base_claude_plugins / "link-plugin"
            link_dir.mkdir(parents=True)
            (link_dir / "hooks").symlink_to(real_dir)
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(base)
            try:
                result = sources.discover_sources()
                hooks_count = sum(1 for s in result if "hooks.json" in str(s.path))
                self.assertEqual(hooks_count, 1, "Symlinked duplicates should be deduped")
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    del os.environ["HOME"]
