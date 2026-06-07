#!/usr/bin/env python3
"""Tests for collect.py (collect-market-overview) — all subprocess.run calls are mocked."""

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
    'collect-market-overview',
    'scripts',
    'collect.py',
)
spec = importlib.util.spec_from_file_location("collect_market_mod", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

SAMPLE_INDEX = {"name": "上证指数", "code": "000001", "price": 3200.50,
                 "changePercent": 0.5, "volume": 2000000000}
SAMPLE_HOT_STOCK = {"name": "贵州茅台", "code": "600519", "rank": 1,
                    "changePercent": 2.3, "heatScore": 95.0}
SAMPLE_SECTOR = {"name": "半导体", "code": "BK0901", "rank": 1,
                 "changePercent": 3.2, "mainNetInflow": 1200000000,
                 "leadStock": "中芯国际", "leadCode": "688981"}


def _mock_process(stdout_data, returncode=0):
    """Build a fake subprocess result."""
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestCollectMarketOverview(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self):
        """Call collect.main() and return parsed output."""
        out_path = os.path.join(self.test_dir, 'out.json')
        argv_save = sys.argv
        try:
            sys.argv = ['collect.py', out_path]
            collect.main()
        finally:
            sys.argv = argv_save
        with open(out_path) as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # 1. All three commands called
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": []}))
    def test_all_three_commands_called(self, mock_run):
        """Should call index-board, hot-rank, and sectors commands."""
        self._run()
        commands_used = []
        for call_args in mock_run.call_args_list:
            args = call_args[0][0]
            commands_used.append(' '.join(args[:3]))
        self.assertIn('opencli eastmoney index-board', commands_used)
        self.assertIn('opencli eastmoney hot-rank', commands_used)
        self.assertIn('opencli eastmoney sectors', commands_used)
        self.assertEqual(mock_run.call_count, 3)

    # ------------------------------------------------------------------ #
    # 2. Partial when one command fails
    # ------------------------------------------------------------------ #

    @patch('subprocess.run')
    def test_partial_when_one_command_fails(self, mock_run):
        """One failure → status 'partial'."""
        mock_run.side_effect = [
            _mock_process({"data": [SAMPLE_INDEX]}),
            _mock_process([], returncode=1),
            _mock_process({"data": [SAMPLE_SECTOR]}),
        ]
        output = self._run()
        self.assertEqual(output['status'], 'partial')
        self.assertGreater(len(output['errors']), 0)

    # ------------------------------------------------------------------ #
    # 3. Output has indices, hot_stocks, sectors
    # ------------------------------------------------------------------ #

    @patch('subprocess.run')
    def test_output_has_all_three_sections(self, mock_run):
        """Output data should contain indices, hot_stocks, and sectors."""
        mock_run.side_effect = [
            _mock_process({"data": [SAMPLE_INDEX]}),
            _mock_process({"data": [SAMPLE_HOT_STOCK]}),
            _mock_process({"data": [SAMPLE_SECTOR]}),
        ]
        output = self._run()
        self.assertIn('indices', output['data'])
        self.assertIn('hot_stocks', output['data'])
        self.assertIn('sectors', output['data'])
        self.assertEqual(len(output['data']['indices']), 1)
        self.assertEqual(len(output['data']['hot_stocks']), 1)
        self.assertEqual(len(output['data']['sectors']), 1)

    # ------------------------------------------------------------------ #
    # 4. Timestamp has timezone
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": []}))
    def test_timestamp_has_timezone(self, mock_run):
        """generated_at must include timezone offset without microseconds."""
        output = self._run()
        ts = output['generated_at']
        self.assertIsNotNone(
            re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts)
        )
        self.assertNotIn('.', ts)


if __name__ == '__main__':
    unittest.main()