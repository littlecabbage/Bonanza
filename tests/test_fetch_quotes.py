#!/usr/bin/env python3
"""Tests for fetch_quotes.py — all subprocess.run calls are mocked."""

import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

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
        "000725": {"name": "京东方A", "market": "a", "aliases": ["000725.SZ"]},
        "00700": {"name": "腾讯控股", "market": "hk", "aliases": ["0700.HK"]},
        "NVDA": {"name": "NVIDIA", "market": "us"},
    }
}

SAMPLE_A_QUOTE = {
    "name": "京东方A", "code": "000725", "market": "a", "price": 4.52,
    "changePercent": 3.5, "open": 4.48, "high": 4.58, "low": 4.45,
    "volume": 124500000, "turnoverRate": 0.82, "pe": 18.5, "pb": 1.4,
    "marketCap": 156000000000,
}


def _mock_process(stdout_data, returncode=0):
    """Build a fake subprocess result."""
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestFetchQuotes(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, input_arg):
        """Call fetch_quotes.main() with the given input and return parsed output."""
        out_path = os.path.join(self.test_dir, 'out.json')
        argv_save = sys.argv
        try:
            sys.argv = ['fetch_quotes.py', input_arg, out_path]
            fetch_quotes.main()
        finally:
            sys.argv = argv_save
        with open(out_path) as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # 1–4: Subprocess command construction
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_a_share_uses_eastmoney_quote(self, mock_run, mock_load):
        """A-share stock calls opencli eastmoney quote (NOT hk-quote/us-quote)."""
        self._run(json.dumps(["000725"]))
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_hk_stock_uses_eastmoney_quote(self, mock_run, mock_load):
        """HK stock calls opencli eastmoney quote (NOT hk-quote)."""
        self._run(json.dumps(["00700"]))
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_us_stock_uses_eastmoney_quote(self, mock_run, mock_load):
        """US stock calls opencli eastmoney quote (NOT us-quote)."""
        self._run(json.dumps(["NVDA"]))
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'eastmoney')
        self.assertEqual(args[2], 'quote')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_multiple_codes_single_batch(self, mock_run, mock_load):
        """Multiple codes produce a single subprocess call."""
        self._run(json.dumps(["000725", "00700"]))
        self.assertEqual(mock_run.call_count, 1)

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_different_markets_single_batch(self, mock_run, mock_load):
        """Different-market codes are batched into one call."""
        self._run(json.dumps(["000725", "NVDA"]))
        self.assertEqual(mock_run.call_count, 1)

    # ------------------------------------------------------------------ #
    # 5: Entity file filtering
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_entities_file_reads_only_stock_type(self, mock_run, mock_load):
        """Only entities where type='stock' are extracted from an entities file."""
        entities = {
            "data": {
                "entities": [
                    {"code": "00700", "type": "stock", "name": "腾讯控股"},
                    {"code": "SOMEFUND", "type": "fund", "name": "某基金"},
                    {"code": "SOMEINDEX", "type": "index", "name": "某指数"},
                ]
            }
        }
        fpath = os.path.join(self.test_dir, 'entities.json')
        with open(fpath, 'w') as f:
            json.dump(entities, f)

        output = self._run(fpath)
        self.assertEqual(output['coverage']['requested'], 1)
        self.assertEqual(mock_run.call_count, 1)

    # ------------------------------------------------------------------ #
    # 6: Deduplication
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_input_deduplication(self, mock_run, mock_load):
        """Duplicate codes produce a single subprocess call with only one code."""
        self._run(json.dumps(["000725", "000725", "000725.SZ"]))
        args = mock_run.call_args[0][0]
        codes = args[3]
        self.assertEqual(codes.count('000725'), 1)

    # ------------------------------------------------------------------ #
    # 7: Unrecognized codes produce errors
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_unrecognized_code_produces_error(self, mock_run, mock_load):
        """Unknown code appears in errors, not silently dropped."""
        output = self._run(json.dumps(["000725", "ZZZZZ_invalid"]))
        self.assertEqual(mock_run.call_count, 1)
        self.assertGreaterEqual(len(output['errors']), 1)
        self.assertTrue(any('ZZZZZ_invalid' in e for e in output['errors']))

    # ------------------------------------------------------------------ #
    # 8–9: Output format parsing
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process([SAMPLE_A_QUOTE]))
    def test_array_output_parsed(self, mock_run, mock_load):
        """Raw JSON array from opencli is parsed correctly."""
        output = self._run(json.dumps(["000725"]))
        self.assertEqual(len(output['data']['quotes']), 1)
        self.assertEqual(output['data']['quotes'][0]['code'], '000725')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_envelope_output_parsed(self, mock_run, mock_load):
        """Envelope {'data': [...]} from opencli is parsed correctly."""
        output = self._run(json.dumps(["000725"]))
        self.assertEqual(len(output['data']['quotes']), 1)
        self.assertEqual(output['data']['quotes'][0]['price'], 4.52)

    # ------------------------------------------------------------------ #
    # 10: CamelCase → snake_case
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_camelcase_normalized_to_snakecase(self, mock_run, mock_load):
        """Fields like changePercent are normalised to change_percent."""
        output = self._run(json.dumps(["000725"]))
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
        mock_run.side_effect = [
            _mock_process({"data": [SAMPLE_A_QUOTE]}),
        ]
        output = self._run(json.dumps(["000725", "UNKNOWN"]))
        self.assertEqual(output['status'], 'partial')

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": []}))
    def test_all_failures_is_failed(self, mock_run, mock_load):
        """All unrecognised codes → status 'failed' (no subprocess call)."""
        output = self._run(json.dumps(["ZZZZZ_invalid"]))
        mock_run.assert_not_called()
        self.assertEqual(output['status'], 'failed')

    # ------------------------------------------------------------------ #
    # 13: Empty input
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run')
    def test_empty_input_distinguished(self, mock_run, mock_load):
        """Empty input is distinct from 'complete' — no subprocess calls."""
        output = self._run(json.dumps([]))
        mock_run.assert_not_called()
        self.assertEqual(output['coverage']['requested'], 0)
        self.assertEqual(output['coverage']['succeeded'], 0)
        self.assertEqual(output['coverage']['failed'], 0)
        self.assertNotEqual(output['status'], 'complete')
        self.assertEqual(output['status'], 'empty')

    # ------------------------------------------------------------------ #
    # 14: Timestamp format
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_timestamp_has_timezone_no_microseconds(self, mock_run, mock_load):
        """generated_at matches ISO 8601 with timezone, no microseconds."""
        output = self._run(json.dumps(["000725"]))
        ts = output['generated_at']
        self.assertIsNotNone(re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
        ))
        self.assertNotIn('.', ts)

    # ------------------------------------------------------------------ #
    # 15: Schema compliance
    # ------------------------------------------------------------------ #

    @patch('fetch_quotes.load_stock_codes', return_value=REF_DATA)
    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_A_QUOTE]}))
    def test_output_matches_schema(self, mock_run, mock_load):
        """All required top-level and quote fields are present."""
        output = self._run(json.dumps(["000725"]))
        for key in ("schema_version", "generated_at", "status", "source", "coverage", "errors", "data"):
            self.assertIn(key, output)
        self.assertEqual(output["schema_version"], "1.0")
        self.assertIn("skill", output["source"])
        self.assertIn("commands", output["source"])
        self.assertEqual(output["source"]["skill"], "fetch-stock-quotes")
        for key in ("requested", "succeeded", "failed"):
            self.assertIn(key, output["coverage"])
        for q in output["data"]["quotes"]:
            for field in ("name", "code", "market", "price"):
                self.assertIn(field, q)
            self.assertIn(q["market"], ("a", "us", "hk"))


if __name__ == '__main__':
    unittest.main()