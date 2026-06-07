#!/usr/bin/env python3
"""Test that all opencli commands in skills/ files reference valid commands."""

import os
import re
import unittest

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

ALLOWED_COMMANDS = {
    "eastmoney": {"index-board", "hot-rank", "sectors", "longhu", "kuaixun",
                  "money-flow", "northbound", "quote", "rank"},
    "twitter": {"tweets", "search", "trending"},
    "xueqiu": {"hot", "hot-stock", "comments", "stock", "search", "feed", "kline"},
    "sinafinance": {"stock"},
    "yahoo_finance": {"quote"},
    "zhihu": {"hot"},
    "reddit": {"hot", "comments"},
}

KNOWN_BAD_COMMANDS = {
    "eastmoney index",
    "eastmoney hot-stocks",
    "eastmoney block-trades",
    "eastmoney fund-flow",
    "eastmoney policy",
    "eastmoney industry",
    "eastmoney discussions",
    "eastmoney hk-quote",
    "eastmoney us-quote",
    "xueqiu hot-topics",
    "twitter blogger-tweets",
}


def find_opencli_commands(filepath):
    """Find all opencli <site> <subcommand> occurrences in a file."""
    commands = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Build alternation from known sites for a tight match
    sites = "|".join(sorted(ALLOWED_COMMANDS.keys(), key=len, reverse=True))
    pattern = rf'opencli\s+({sites})\s+([a-zA-Z][a-zA-Z0-9_-]*)'
    for match in re.finditer(pattern, content, re.IGNORECASE):
        site = match.group(1).lower()
        subcmd = match.group(2).lower()
        commands.append((site, subcmd))
    return commands


def is_allowed(site, subcommand):
    """Check if a (site, subcommand) pair is in the allowed set."""
    if site in ALLOWED_COMMANDS:
        return subcommand in ALLOWED_COMMANDS[site]
    return False


class TestOpencliCommands(unittest.TestCase):

    def _iter_skill_files(self):
        """Yield paths to all SKILL.md files under skills/."""
        for root, dirs, files in os.walk(SKILLS_DIR):
            for f in files:
                if f == "SKILL.md":
                    yield os.path.join(root, f)
                elif f.endswith(".py"):
                    yield os.path.join(root, f)

    def test_all_commands_are_allowed(self):
        """Every opencli command in SKILL.md and .py files must be in the allowed set."""
        bad = []
        for filepath in sorted(self._iter_skill_files()):
            for site, subcmd in find_opencli_commands(filepath):
                if not is_allowed(site, subcmd):
                    bad.append((filepath, site, subcmd))
        if bad:
            msg = "\n".join(
                f"  {fp}: opencli {site} {subcmd} (not in allowed set)"
                for fp, site, subcmd in bad
            )
            self.fail(f"Found disallowed opencli commands:\n{msg}")

    def test_no_known_bad_commands(self):
        """Grep for known bad command patterns and assert zero hits."""
        hits = []
        for filepath in sorted(self._iter_skill_files()):
            for site, subcmd in find_opencli_commands(filepath):
                full = f"{site} {subcmd}"
                if full in KNOWN_BAD_COMMANDS:
                    hits.append((filepath, full))
        if hits:
            msg = "\n".join(
                f"  {fp}: opencli {bad}" for fp, bad in hits
            )
            self.fail(f"Found known bad commands that should have been removed:\n{msg}")


if __name__ == "__main__":
    unittest.main()