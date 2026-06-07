#!/usr/bin/env python3
"""Tests for collect.py (collect-market-sentiment) — all subprocess.run calls are mocked."""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills',
    'collect-market-sentiment',
    'scripts',
    'collect.py',
)
spec = importlib.util.spec_from_file_location("collect_market_sentiment_mod", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

SAMPLE_HOT_STOCK = {
    "name": "贵州茅台", "symbol": "600519", "rank": 1,
    "change_percent": 2.5, "heat_score": 95.0,
}
SAMPLE_HOT_POST = {
    "title": "白酒板块回暖", "url": "https://xueqiu.com/123",
    "created_at": "2026-06-07T10:00:00", "mentions": 42,
}


def _mock_process(stdout_data, returncode=0):
    """Build a fake subprocess result."""
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestCollectMarketSentiment(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, output_filename=None):
        """Call collect.main() and return parsed output."""
        if output_filename is None:
            output_filename = 'out.json'
        out_path = os.path.join(self.test_dir, output_filename)
        argv_save = sys.argv
        try:
            sys.argv = ['collect.py', out_path]
            collect.main()
        finally:
            sys.argv = argv_save
        with open(out_path) as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # 1–2: Command construction
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_HOT_STOCK]}))
    def test_hot_stock_command(self, mock_run):
        """Calls opencli xueqiu hot-stock --limit N -f json."""
        self._run()
        args = mock_run.call_args_list[0][0][0]
        self.assertEqual(args[0], 'opencli')
        self.assertEqual(args[1], 'xueqiu')
        self.assertEqual(args[2], 'hot-stock')
        self.assertIn('--limit', args)
        self.assertIn('-f', args)

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_HOT_STOCK]}))
    def test_default_limit(self, mock_run):
        """Default --limit should be passed as a string digit."""
        self._run()
        args = mock_run.call_args_list[0][0][0]
        limit_idx = args.index('--limit') + 1
        self.assertTrue(args[limit_idx].isdigit())

    # ------------------------------------------------------------------ #
    # 3: Output schema structure
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK, SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST, SAMPLE_HOT_POST]}),
    ])
    def test_output_has_schema_fields(self, mock_run):
        """Output contains all required envelope fields."""
        output = self._run()
        for key in ("schema_version", "generated_at", "status", "source",
                     "coverage", "errors", "data"):
            self.assertIn(key, output)
        self.assertEqual(output["schema_version"], "1.0")

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_data_has_both_sections(self, mock_run):
        """data contains xueqiu_hot_stocks and xueqiu_hot_posts."""
        output = self._run()
        self.assertIn("xueqiu_hot_stocks", output["data"])
        self.assertIn("xueqiu_hot_posts", output["data"])

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_source_skill_correct(self, mock_run):
        """source.skill should be collect-market-sentiment."""
        output = self._run()
        self.assertEqual(output["source"]["skill"], "collect-market-sentiment")

    # ------------------------------------------------------------------ #
    # 4: Partial / failed handling
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        Exception("Network error"),
    ])
    def test_one_failure_is_partial(self, mock_run):
        """One command fails, other succeeds → status 'partial'."""
        output = self._run()
        self.assertEqual(output['status'], 'partial')
        self.assertGreaterEqual(len(output['errors']), 1)

    @patch('subprocess.run', side_effect=[
        Exception("Error A"),
        Exception("Error B"),
    ])
    def test_all_failures_is_failed(self, mock_run):
        """Both commands fail → status 'failed'."""
        output = self._run()
        self.assertEqual(output['status'], 'failed')
        self.assertGreaterEqual(len(output['errors']), 2)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_all_succeed_is_complete(self, mock_run):
        """Both commands succeed → status 'complete'."""
        output = self._run()
        self.assertEqual(output['status'], 'complete')
        self.assertEqual(len(output['errors']), 0)

    # ------------------------------------------------------------------ #
    # 5: Error recording
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": []}, returncode=1),
    ])
    def test_errors_are_strings(self, mock_run):
        """Error entries must be strings, not exception objects."""
        output = self._run()
        for e in output['errors']:
            self.assertIsInstance(e, str)

    # ------------------------------------------------------------------ #
    # 6: Timestamp format
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_timestamp_has_timezone_no_microseconds(self, mock_run):
        """generated_at matches ISO 8601 with timezone, no microseconds."""
        output = self._run()
        ts = output['generated_at']
        self.assertIsNotNone(re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
        ))
        self.assertNotIn('.', ts)

    # ------------------------------------------------------------------ #
    # 7: Coverage tracking
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_coverage_fields_present(self, mock_run):
        """coverage has requested/succeeded/failed."""
        output = self._run()
        for key in ("requested", "succeeded", "failed"):
            self.assertIn(key, output["coverage"])
        self.assertEqual(output["coverage"]["requested"], 2)
        self.assertEqual(output["coverage"]["succeeded"], 2)
        self.assertEqual(output["coverage"]["failed"], 0)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        Exception("Error"),
    ])
    def test_coverage_partial_counts(self, mock_run):
        """Partial: 2 requested, 1 succeeded, 1 failed."""
        output = self._run()
        self.assertEqual(output["coverage"]["succeeded"], 1)
        self.assertEqual(output["coverage"]["failed"], 1)

    # ------------------------------------------------------------------ #
    # 8: Commands recorded in source
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_HOT_STOCK]}),
        _mock_process({"data": [SAMPLE_HOT_POST]}),
    ])
    def test_commands_recorded(self, mock_run):
        """source.commands lists the commands that succeeded."""
        output = self._run()
        self.assertIsInstance(output["source"]["commands"], list)
        self.assertGreaterEqual(len(output["source"]["commands"]), 1)


if __name__ == '__main__':
    unittest.main()
