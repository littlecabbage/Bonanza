#!/usr/bin/env python3
"""Tests for fetch_quotes.py — all subprocess.run calls are mocked."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills',
    'fetch-stock-quotes',
    'scripts'
)
sys.path.insert(0, SCRIPT_DIR)

import fetch_quotes

REF_DATA = {
    "version": "1",
    "stocks": {
        "000725": {
            "name": "京东方A",
            "market": "a",
            "aliases": ["000725.SZ"]
        },
        "00700": {
            "name": "腾讯控股",
            "market": "hk",
            "aliases": ["0700.HK"]
        },
        "NVDA": {
            "name": "NVIDIA",
            "market": "us"
        },
        "TSLA": {
            "name": "Tesla",
            "market": "us",
            "aliases": ["TSLA.US"]
        }
    }
}

SAMPLE_A_QUOTE = {
    "name": "京东方A",
    "code": "000725",
    "market": "a",
    "price": 4.52,
    "changePercent": 3.5,
    "open": 4.48,
    "high": 4.58,
    "low": 4.45,
    "volume": 124500000,
    "turnoverRate": 0.82,
    "pe": 18.5,
    "pb": 1.4,
    "marketCap": 156000000000
}

SAMPLE_HK_QUOTE = {
    "name": "腾讯控股",
    "code": "00700",
    "market": "hk",
    "price": 380.0,
    "changePercent": 1.2,
    "open": 376.0,
    "high": 382.0,
    "low": 375.0,
    "volume": 8500000,
    "turnoverRate": 0.15,
    "pe": 25.0,
    "pb": 5.2,
    "marketCap": 3600000000000
}

SAMPLE_US_QUOTE = {
    "name": "NVIDIA",
    "code": "NVDA",
    "market": "us",
    "price": 135.0,
    "changePercent": 2.1,
    "open": 132.0,
    "high": 136.5,
    "low": 131.5,
    "volume": 45000000,
    "turnoverRate": None,
    "pe": 65.0,
    "pb": None,
    "marketCap": 33000000000000
}


def _mock_subprocess(stdout_data, returncode=0):
    """Create a mock that returns a completed process with given stdout."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = json.dumps(stdout_data)
    proc.stderr = ""
    mock = MagicMock(return_value=proc)
    return mock


class TestFetchQuotes(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # 1–4: Subprocess command construction
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_a_share_uses_eastmoney_quote(self, mock_run, mock_load):
        """A-share stock calls opencli eastmoney quote (NOT hk-quote/us-quote)."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_hk_stock_uses_eastmoney_quote(self, mock_run, mock_load):
        """HK stock calls opencli eastmoney quote (NOT hk-quote)."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_HK_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["00700"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_us_stock_uses_eastmoney_quote(self, mock_run, mock_load):
        """US stock calls opencli eastmoney quote (NOT us-quote)."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_US_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["NVDA"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_multiple_codes_single_batch(self, mock_run, mock_load):
        """Multiple codes of the same market produce one command."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725", "000725.SZ"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        # Even with duplicates/resolved aliases, only one subprocess call
        self.assertEqual(mock_run.call_count, 1)

    # ------------------------------------------------------------------ #
    # 5: Entity file filtering
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_entities_file_reads_only_stock_type(self, mock_run, mock_load):
        """Only entities where type='stock' are extracted from an entities file."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        entities = {
            "data": {
                "entities": [
                    {"code": "000725", "type": "stock", "name": "京东方A"},
                    {"code": "00700", "type": "stock", "name": "腾讯控股"},
                    {"code": "SOMEFUND", "type": "fund", "name": "某基金"},
                    {"code": "SOMEINDEX", "type": "index", "name": "某指数"},
                ]
            }
        }
        fpath = os.path.join(self.test_dir, 'entities.json')
        with open(fpath, 'w') as f:
            json.dump(entities, f)

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', fpath, os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        # Load the output and verify
        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        # Only 2 stocks, not 4 entities
        # But since 00700 is hk, only a-share codes get processed in this call
        self.assertEqual(output['coverage']['requested'], 2)

    # ------------------------------------------------------------------ #
    # 6: Deduplication
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_input_deduplication(self, mock_run, mock_load):
        """Duplicate codes produce a single subprocess call with only one code."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725", "000725", "000725.SZ"]),
                    os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        # The command args should only have each code once
        args = mock_run.call_args[0][0]
        # Should only contain one occurrence of 000725 in the codes argument
        codes = args[3]
        self.assertIn('000725', codes)
        # The code should appear only once in the comma-separated list
        self.assertEqual(codes.count('000725'), 1)

    # ------------------------------------------------------------------ #
    # 7: Unrecognized codes produce errors
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_unrecognized_code_produces_error(self, mock_run, mock_load):
        """An unrecognised code appears in errors, not silently dropped."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725", "ZZZZZ"]),
                    os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertGreaterEqual(len(output['errors']), 1)
        self.assertTrue(any('ZZZZZ' in e for e in output['errors']))

    # ------------------------------------------------------------------ #
    # 8–9: Output format parsing
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_array_output_parsed(self, mock_run, mock_load):
        """When opencli returns a JSON array, it is still parsed correctly."""
        mock_run.side_effect = [
            _mock_subprocess([SAMPLE_A_QUOTE]),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertEqual(len(output['data']['quotes']), 1)
        self.assertEqual(output['data']['quotes'][0]['code'], '000725')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_envelope_output_parsed(self, mock_run, mock_load):
        """When opencli returns {'data': [...]}, it is parsed correctly."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertEqual(len(output['data']['quotes']), 1)
        self.assertEqual(output['data']['quotes'][0]['price'], 4.52)

    # ------------------------------------------------------------------ #
    # 10: CamelCase → snake_case
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_camelcase_normalized_to_snakecase(self, mock_run, mock_load):
        """Fields like changePercent are normalised to change_percent."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        quote = output['data']['quotes'][0]
        self.assertIn('change_percent', quote)
        self.assertNotIn('changePercent', quote)
        self.assertIn('turnover_rate', quote)
        self.assertNotIn('turnoverRate', quote)
        self.assertIn('market_cap', quote)
        self.assertNotIn('marketCap', quote)
        self.assertEqual(quote['change_percent'], 3.5)

    # ------------------------------------------------------------------ #
    # 11–12: Status logic
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_single_failure_is_partial(self, mock_run, mock_load):
        """One quote fails, others succeed → status 'partial'."""
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if '000725' in cmd[3]:
                return _mock_subprocess({"data": [SAMPLE_A_QUOTE]})()
            return _mock_subprocess({}, 0)() if False else _mock_subprocess({"data": []})()
        mock_run.side_effect = None
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"data": []}))

        # We'll run with two codes that should both be a-shares; one familiar, one unknown
        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725", "999999"]),
                    os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertEqual(output['status'], 'partial')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_all_failures_is_failed(self, mock_run, mock_load):
        """All quotes fail → status 'failed'."""
        mock_run.side_effect = [
            _mock_subprocess({"data": []}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["ZZZZZ"]),
                    os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertEqual(output['status'], 'failed')

    # ------------------------------------------------------------------ #
    # 13: Empty input
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_empty_input_distinguished(self, mock_run, mock_load):
        """Empty input is distinct from 'complete' — no subprocess calls."""
        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps([]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        mock_run.assert_not_called()
        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        self.assertEqual(output['coverage']['requested'], 0)
        self.assertEqual(output['coverage']['succeeded'], 0)
        self.assertEqual(output['coverage']['failed'], 0)
        # Empty input should not be "complete"
        self.assertNotEqual(output['status'], 'complete')

    # ------------------------------------------------------------------ #
    # 14: Timestamp format
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_timestamp_has_timezone_no_microseconds(self, mock_run, mock_load):
        """generated_at matches ISO 8601 with timezone, no microseconds."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725"]), os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)
        ts = output['generated_at']
        # Must match pattern: 2026-06-07T10:30:00+08:00
        import re
        self.assertIsNotNone(re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
        ))
        # Must NOT contain microseconds (no dot)
        self.assertNotIn('.', ts)

    # ------------------------------------------------------------------ #
    # 15: Schema compliance
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_output_matches_schema(self, mock_run, mock_load):
        """All required top-level and quote fields are present."""
        mock_run.side_effect = [
            _mock_subprocess({"data": [SAMPLE_A_QUOTE, SAMPLE_US_QUOTE]}),
        ]

        argv_save = sys.argv
        sys.argv = ['fetch_quotes.py', json.dumps(["000725", "NVDA"]),
                    os.path.join(self.test_dir, 'out.json')]
        try:
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(os.path.join(self.test_dir, 'out.json')) as f:
            output = json.load(f)

        # Top-level required fields
        for key in ("schema_version", "generated_at", "status", "source", "coverage", "errors", "data"):
            self.assertIn(key, output)

        # schema_version
        self.assertEqual(output["schema_version"], "1.0")

        # source
        self.assertIn("skill", output["source"])
        self.assertIn("commands", output["source"])
        self.assertEqual(output["source"]["skill"], "fetch-stock-quotes")

        # coverage
        for key in ("requested", "succeeded", "failed"):
            self.assertIn(key, output["coverage"])

        # Each quote must have name, code, market, price
        for q in output["data"]["quotes"]:
            for field in ("name", "code", "market", "price"):
                self.assertIn(field, q)
            self.assertIn(q["market"], ("a", "us", "hk"))


if __name__ == '__main__':
    unittest.main()