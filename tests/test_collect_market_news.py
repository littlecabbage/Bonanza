#!/usr/bin/env python3
"""Tests for collect.py (collect-market-news) — all subprocess.run calls are mocked."""

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
    'collect-market-news',
    'scripts',
    'collect.py',
)
spec = importlib.util.spec_from_file_location("collect_market_news_mod", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

SAMPLE_KUAIXUN = {
    "title": "央行宣布降准0.5个百分点",
    "summary": "中国人民银行决定于2026年6月15日下调金融机构存款准备金率",
    "time": "2026-06-07 09:00:00",
    "priority": "high",
}
SAMPLE_ZHIHU = {
    "title": "如何看待央行降准？",
    "url": "https://www.zhihu.com/question/123",
    "rank": 1,
    "finance_relation": "direct",
}


def _mock_process(stdout_data, returncode=0):
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestCollectMarketNews(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, output_filename=None):
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

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_kuaixun_command(self, mock_run):
        """First command is opencli eastmoney kuaixun --limit N -f json."""
        self._run()
        args = mock_run.call_args_list[0][0][0]
        self.assertEqual(args[0], 'opencli')
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'kuaixun')
        self.assertIn('--limit', args)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_zhihu_command(self, mock_run):
        """Second command is opencli zhihu hot --limit N -f json."""
        self._run()
        args = mock_run.call_args_list[1][0][0]
        self.assertEqual(args[1], 'zhihu')
        self.assertEqual(args[2], 'hot')
        self.assertIn('--limit', args)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_default_limit(self, mock_run):
        """Default --limit should be passed as a string digit."""
        self._run()
        args = mock_run.call_args_list[0][0][0]
        limit_idx = args.index('--limit') + 1
        self.assertTrue(args[limit_idx].isdigit())

    # ------------------------------------------------------------------ #
    # 3: Output schema
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_data_has_both_sections(self, mock_run):
        """data contains kuaixun and zhihu_hot."""
        output = self._run()
        self.assertIn("kuaixun", output["data"])
        self.assertIn("zhihu_hot", output["data"])

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_source_skill_correct(self, mock_run):
        """source.skill should be collect-market-news."""
        output = self._run()
        self.assertEqual(output["source"]["skill"], "collect-market-news")

    # ------------------------------------------------------------------ #
    # 4–6: Status
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        Exception("Zhihu error"),
    ])
    def test_one_failure_is_partial(self, mock_run):
        """One fails, one succeeds → status 'partial'."""
        output = self._run()
        self.assertEqual(output['status'], 'partial')
        self.assertGreaterEqual(len(output['errors']), 1)

    @patch('subprocess.run', side_effect=[
        Exception("Error A"),
        Exception("Error B"),
    ])
    def test_all_failures_is_failed(self, mock_run):
        """Both fail → status 'failed'."""
        output = self._run()
        self.assertEqual(output['status'], 'failed')
        self.assertGreaterEqual(len(output['errors']), 2)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_all_succeed_is_complete(self, mock_run):
        """Both succeed → status 'complete'."""
        output = self._run()
        self.assertEqual(output['status'], 'complete')
        self.assertEqual(len(output['errors']), 0)

    # ------------------------------------------------------------------ #
    # 7: Coverage
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_coverage_all_success(self, mock_run):
        """2 requested, 2 succeeded, 0 failed."""
        output = self._run()
        self.assertEqual(output["coverage"]["requested"], 2)
        self.assertEqual(output["coverage"]["succeeded"], 2)
        self.assertEqual(output["coverage"]["failed"], 0)

    @patch('subprocess.run', side_effect=[
        Exception("Err"),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_coverage_partial_counts(self, mock_run):
        """2 requested, 1 succeeded, 1 failed."""
        output = self._run()
        self.assertEqual(output["coverage"]["succeeded"], 1)
        self.assertEqual(output["coverage"]["failed"], 1)

    # ------------------------------------------------------------------ #
    # 8: Timestamp
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_KUAIXUN]}),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_timestamp_has_timezone_no_microseconds(self, mock_run):
        """generated_at matches ISO 8601 with timezone."""
        output = self._run()
        ts = output['generated_at']
        self.assertIsNotNone(re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
        ))
        self.assertNotIn('.', ts)

    # ------------------------------------------------------------------ #
    # 9: Errors are strings
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        Exception("Connection timeout"),
        _mock_process({"data": [SAMPLE_ZHIHU]}),
    ])
    def test_errors_are_strings(self, mock_run):
        """Error entries must be strings."""
        output = self._run()
        for e in output['errors']:
            self.assertIsInstance(e, str)


if __name__ == '__main__':
    unittest.main()
