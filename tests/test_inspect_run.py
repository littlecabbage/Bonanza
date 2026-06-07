#!/usr/bin/env python3
"""Tests for the inspect_run.py state machine.

Tests cover status-aware categorization: completed_steps, usable_products,
stale_products, failed_products, invalid_products, and fresh-based
recommendation logic.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

# Ensure the script is importable
SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills',
    'guide-investment-workflow',
    'scripts'
)
sys.path.insert(0, SCRIPT_DIR)

import inspect_run


def _iso(offset_hours=None):
    """Generate an ISO 8601 timestamp, optionally offset from now."""
    dt = datetime.now(timezone.utc)
    if offset_hours is not None:
        dt += timedelta(hours=offset_hours)
    return dt.replace(microsecond=0).isoformat()


VALID_PRODUCT = {
    "schema_version": "1.0",
    "generated_at": _iso(-1),  # 1 hour ago = fresh
    "status": "complete",
    "source": {"skill": "collect-market-overview", "commands": ["test"]},
    "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
    "errors": [],
    "data": {}
}


class TestInspectRun(unittest.TestCase):
    """Inspect run state machine tests."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_json(self, relpath, data):
        fpath = os.path.join(self.test_dir, relpath)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def _write_text(self, relpath, text):
        fpath = os.path.join(self.test_dir, relpath)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(text)

    def _run(self):
        return inspect_run.inspect_run(self.test_dir)

    def _state(self, steps=None, status="partial"):
        return {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "test-001",
            "status": status,
            "steps": steps or []
        }

    def test_complete_status_is_recognized(self):
        """Step with status 'complete' appears in completed_steps."""
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-market-overview", "status": "complete",
             "output_file": "market-overview.json"}
        ]))
        self._write_json("market-overview.json", VALID_PRODUCT)

        result = self._run()
        self.assertIn("collect-market-overview", result["completed_steps"])

    def test_partial_is_usable_but_not_complete(self):
        """Product with status 'partial' is usable but NOT in completed_steps."""
        fresh_partial = dict(VALID_PRODUCT, status="partial", generated_at=_iso(-1))
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-market-sentiment", "status": "partial",
             "output_file": "market-sentiment.json"}
        ]))
        self._write_json("market-sentiment.json", fresh_partial)

        result = self._run()
        self.assertNotIn("collect-market-sentiment", result["completed_steps"])
        self.assertIn("market-sentiment.json", result["usable_products"])

    def test_failed_not_completed(self):
        """Step with status 'failed' goes to failed_products, not completed_steps."""
        failed_product = dict(VALID_PRODUCT, status="failed", generated_at=_iso(-1))
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-blogger-updates", "status": "failed",
             "output_file": "blogger-updates.json", "errors": ["Boom"]}
        ]))
        self._write_json("blogger-updates.json", failed_product)

        result = self._run()
        self.assertNotIn("collect-blogger-updates", result["completed_steps"])
        self.assertIn("blogger-updates.json", result["failed_products"])

    def test_corrupt_json_not_completed(self):
        """Product with invalid JSON goes to invalid_products, not completed_steps."""
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-market-overview", "status": "complete",
             "output_file": "market-overview.json"}
        ]))
        self._write_text("market-overview.json", "this is not json")

        result = self._run()
        self.assertNotIn("collect-market-overview", result["completed_steps"])
        self.assertIn("market-overview.json", result["invalid_products"])

    def test_stale_product_recommends_recollection(self):
        """Product older than 4 hours triggers recollection recommendation."""
        stale_product = dict(VALID_PRODUCT, generated_at=_iso(-5))
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-market-overview", "status": "complete",
             "output_file": "market-overview.json"}
        ]))
        self._write_json("market-overview.json", stale_product)

        result = self._run()
        # Even though it has a product file, the stale product should not
        # block recollection — the step should be recommended again
        next_skills = {r["skill"] for r in result["recommended_next_steps"]}
        self.assertIn("collect-market-overview", next_skills)

    def test_fresh_product_not_rerecommended(self):
        """Fresh product (1 hour old) should NOT be re-recommended."""
        fresh_product = dict(VALID_PRODUCT, generated_at=_iso(-1))
        self._write_json("workflow-state.json", self._state([
            {"skill": "collect-market-overview", "status": "complete",
             "output_file": "market-overview.json"}
        ]))
        self._write_json("market-overview.json", fresh_product)

        result = self._run()
        next_skills = {r["skill"] for r in result["recommended_next_steps"]}
        self.assertNotIn("collect-market-overview", next_skills)

    def test_max_three_recommendations(self):
        """Never more than 3 recommended next steps."""
        # No steps at all → many pending → capped at 3
        self._write_json("workflow-state.json", self._state([]))

        result = self._run()
        self.assertLessEqual(len(result["recommended_next_steps"]), 3)

    def test_missing_run_dir_returns_error(self):
        """Nonexistent run directory returns error dict, no exception."""
        fake_path = "/tmp/nonexistent-run-dir-12345"
        result = inspect_run.inspect_run(fake_path)
        self.assertIn("error", result)
        self.assertIn(fake_path, result["error"])

    def test_corrupt_workflow_state_no_traceback(self):
        """Corrupt workflow-state.json returns gracefully."""
        self._write_text("workflow-state.json", "corrupt {{{ json")

        result = self._run()
        # Should not crash — should return a valid result dict
        self.assertIsInstance(result, dict)
        # completed_steps should at least be defined (possibly empty)
        self.assertIn("completed_steps", result)


if __name__ == '__main__':
    unittest.main()