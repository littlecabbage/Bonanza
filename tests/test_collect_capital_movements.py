#!/usr/bin/env python3
"""Tests for collect.py (collect-capital-movements) — all subprocess.run calls are mocked."""

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
    'collect-capital-movements',
    'scripts',
    'collect.py',
)
spec = importlib.util.spec_from_file_location("collect_capital_movements_mod", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

SAMPLE_LONGHU = {
    "name": "贵州茅台", "code": "600519", "reason": "日涨幅偏离值达7%",
    "change_rate": 10.0, "net_amt": 12345678.0, "turnover": 500000000.0,
}
SAMPLE_MONEY_FLOW = {
    "name": "白酒板块", "code": "BK0477",
    "main_net_inflow": 250000000.0, "change_percent": 3.2,
}
SAMPLE_NORTHBOUND = {
    "date": "2026-06-05", "net_buy": 850000000.0,
    "sh_buy": 500000000.0, "sz_buy": 350000000.0,
}


def _mock_process(stdout_data, returncode=0):
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestCollectCapitalMovements(unittest.TestCase):

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
    # 1–3: Command construction
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_longhu_command(self, mock_run):
        """First command is opencli eastmoney longhu -f json."""
        self._run()
        args = mock_run.call_args_list[0][0][0]
        self.assertEqual(args[0], 'opencli')
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'longhu')
        self.assertIn('-f', args)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_money_flow_command(self, mock_run):
        """Second command is opencli eastmoney money-flow -f json."""
        self._run()
        args = mock_run.call_args_list[1][0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'money-flow')

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_northbound_command(self, mock_run):
        """Third command is opencli eastmoney northbound -f json."""
        self._run()
        args = mock_run.call_args_list[2][0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'northbound')

    # ------------------------------------------------------------------ #
    # 4: Output schema
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_data_has_three_sections(self, mock_run):
        """data contains longhu, money_flow, northbound."""
        output = self._run()
        self.assertIn("longhu", output["data"])
        self.assertIn("money_flow", output["data"])
        self.assertIn("northbound", output["data"])

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_source_skill_correct(self, mock_run):
        """source.skill should be collect-capital-movements."""
        output = self._run()
        self.assertEqual(output["source"]["skill"], "collect-capital-movements")

    # ------------------------------------------------------------------ #
    # 5–7: Status handling
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        Exception("Longhu error"),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_one_failure_is_partial(self, mock_run):
        """One fails, two succeed → status 'partial'."""
        output = self._run()
        self.assertEqual(output['status'], 'partial')
        self.assertGreaterEqual(len(output['errors']), 1)

    @patch('subprocess.run', side_effect=[
        Exception("Error A"),
        Exception("Error B"),
        Exception("Error C"),
    ])
    def test_all_failures_is_failed(self, mock_run):
        """All three fail → status 'failed'."""
        output = self._run()
        self.assertEqual(output['status'], 'failed')
        self.assertGreaterEqual(len(output['errors']), 3)

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_all_succeed_is_complete(self, mock_run):
        """All three succeed → status 'complete'."""
        output = self._run()
        self.assertEqual(output['status'], 'complete')
        self.assertEqual(len(output['errors']), 0)

    # ------------------------------------------------------------------ #
    # 8: Coverage counts
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_coverage_all_success(self, mock_run):
        """3 requested, 3 succeeded, 0 failed."""
        output = self._run()
        self.assertEqual(output["coverage"]["requested"], 3)
        self.assertEqual(output["coverage"]["succeeded"], 3)
        self.assertEqual(output["coverage"]["failed"], 0)

    @patch('subprocess.run', side_effect=[
        Exception("Err"),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        Exception("Err"),
    ])
    def test_coverage_partial_counts(self, mock_run):
        """3 requested, 1 succeeded, 2 failed."""
        output = self._run()
        self.assertEqual(output["coverage"]["succeeded"], 1)
        self.assertEqual(output["coverage"]["failed"], 2)

    # ------------------------------------------------------------------ #
    # 9: Timestamp format
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        _mock_process({"data": [SAMPLE_LONGHU]}),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
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
    # 10: Errors are strings
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', side_effect=[
        Exception("Connection refused"),
        _mock_process({"data": [SAMPLE_MONEY_FLOW]}),
        _mock_process({"data": [SAMPLE_NORTHBOUND]}),
    ])
    def test_errors_are_strings(self, mock_run):
        """Error entries must be strings."""
        output = self._run()
        for e in output['errors']:
            self.assertIsInstance(e, str)


if __name__ == '__main__':
    unittest.main()
