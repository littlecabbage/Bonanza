#!/usr/bin/env python3
"""Tests for analyze_signals.py — all file reads are mocked via temp files.

Test cases cover:
  - Only overview input -> low coverage
  - More inputs -> higher coverage
  - Full input -> four dimensions present
  - Contradictory data placed in both evidence types
  - Missing data listed in each dimension
  - No "强烈买入" or return promises in output
  - Output matches schema
  - Corrupt input handled gracefully
"""

import json
import os
import re
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills',
    'analyze-investment-signals',
    'scripts'
)
sys.path.insert(0, SCRIPT_DIR)

import analyze_signals as sig

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO_ROOT, 'schemas', 'investment-signals.schema.json')
with open(SCHEMA_PATH, encoding='utf-8') as f:
    SCHEMA = json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(dirpath, filename, data):
    path = os.path.join(dirpath, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _run_through_main(file_args, tmpdir):
    """Simulate main() by writing temp files and calling main."""
    argv_save = sys.argv
    out_path = os.path.join(tmpdir, 'out.json')
    try:
        sys.argv = ['analyze_signals.py'] + list(file_args) + [out_path]
        sig.main()
    finally:
        sys.argv = argv_save
    with open(out_path, encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_OVERVIEW = {
    "status": "complete",
    "data": {
        "market": "A股",
        "indexes": [
            {"name": "上证指数", "change_percent": 0.5}
        ]
    }
}

SAMPLE_QUOTES = {
    "data": {
        "quotes": [
            {
                "name": "平安银行",
                "code": "000001",
                "market": "a",
                "price": 12.50,
                "change_percent": 2.88,
                "volume": 50000000,
            },
            {
                "name": "贵州茅台",
                "code": "600519",
                "market": "a",
                "price": 1800.00,
                "change_percent": -0.50,
                "volume": 3000000,
            },
        ]
    }
}

SAMPLE_CAPITAL = {
    "data": {
        "movements": [
            {"name": "北向资金", "net_amount": 50000000, "direction": "in"},
            {"name": "主力资金", "net_amount": -20000000, "direction": "out"},
        ]
    }
}

SAMPLE_BLOGGER = {
    "data": {
        "bloggers": [
            {"username": "大V张三", "sentiment": "positive"},
            {"username": "分析师李四", "sentiment": "negative"},
        ]
    }
}

SAMPLE_SENTIMENT = {
    "data": {
        "sentiment_score": 0.35
    }
}

SAMPLE_NEWS = {
    "data": {
        "news": [
            {"title": "央行降息利好市场", "sentiment": "positive"},
            {"title": "某公司业绩不及预期", "sentiment": "negative"},
        ]
    }
}


class TestAnalyzeSignals(unittest.TestCase):

    # ------------------------------------------------------------------ #
    # 1. Only overview -> low coverage
    # ------------------------------------------------------------------ #

    def test_only_overview_low_coverage(self):
        """Only overview file provided -> coverage_rate < 0.5, confidence low."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_json(tmp, 'overview.json', SAMPLE_OVERVIEW)
            out = _run_through_main([os.path.join(tmp, 'overview.json')], tmp)
        self.assertEqual(out['data']['confidence'], 'low')
        self.assertLess(out['data']['coverage_rate'], 0.5)
        # Only event dimension might have data from overview — let's check
        dims_with_data = sum(
            1 for d in out['data']['dimensions']
            if d['supporting_evidence'] or d['opposing_evidence']
        )
        self.assertLessEqual(dims_with_data, 1)

    # ------------------------------------------------------------------ #
    # 2. More inputs -> higher coverage
    # ------------------------------------------------------------------ #

    def test_two_inputs_medium_coverage(self):
        """Two input files with data from different dimensions -> coverage >= 0.5."""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            p2 = _write_json(tmp, 'capital.json', SAMPLE_CAPITAL)
            out = _run_through_main([p1, p2], tmp)
        self.assertGreaterEqual(out['data']['coverage_rate'], 0.5)
        self.assertIn(out['data']['confidence'], ('medium', 'high'))

    # ------------------------------------------------------------------ #
    # 3. Full input -> four dimensions
    # ------------------------------------------------------------------ #

    def test_full_input_four_dimensions(self):
        """All six input files provided -> all four dimensions present in output."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = [
                _write_json(tmp, 'overview.json', SAMPLE_OVERVIEW),
                _write_json(tmp, 'quotes.json', SAMPLE_QUOTES),
                _write_json(tmp, 'capital.json', SAMPLE_CAPITAL),
                _write_json(tmp, 'blogger.json', SAMPLE_BLOGGER),
                _write_json(tmp, 'sentiment.json', SAMPLE_SENTIMENT),
                _write_json(tmp, 'news.json', SAMPLE_NEWS),
            ]
            out = _run_through_main(paths, tmp)
        names = [d['name'] for d in out['data']['dimensions']]
        self.assertIn('price', names)
        self.assertIn('capital', names)
        self.assertIn('sentiment', names)
        self.assertIn('event', names)

    # ------------------------------------------------------------------ #
    # 4. Contradictory data in both evidence types
    # ------------------------------------------------------------------ #

    def test_contradictory_evidence_types(self):
        """When data has both positive and negative signals, both evidence lists populated."""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            p2 = _write_json(tmp, 'capital.json', SAMPLE_CAPITAL)
            out = _run_through_main([p1, p2], tmp)
        for dim in out['data']['dimensions']:
            if dim['name'] == 'price':
                self.assertTrue(dim['supporting_evidence'])
                self.assertTrue(dim['opposing_evidence'])
            if dim['name'] == 'capital':
                self.assertTrue(dim['supporting_evidence'])
                self.assertTrue(dim['opposing_evidence'])

    # ------------------------------------------------------------------ #
    # 5. Missing data listed
    # ------------------------------------------------------------------ #

    def test_missing_data_listed(self):
        """Dimensions without any input should list missing_data."""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            out = _run_through_main([p1], tmp)
        dims = {d['name']: d for d in out['data']['dimensions']}
        # capital, sentiment, event should have missing_data
        for dim_name in ('capital', 'sentiment', 'event'):
            self.assertTrue(dims[dim_name]['missing_data'],
                            f"{dim_name} should list missing data")
        # price should not list missing_data (it has data)
        self.assertFalse(dims['price']['missing_data'])

    # ------------------------------------------------------------------ #
    # 6. No "强烈买入" or return promises
    # ------------------------------------------------------------------ #

    def test_no_buy_recommendations(self):
        """Output text must not contain '强烈买入' or return promises."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = [
                _write_json(tmp, 'overview.json', SAMPLE_OVERVIEW),
                _write_json(tmp, 'quotes.json', SAMPLE_QUOTES),
                _write_json(tmp, 'capital.json', SAMPLE_CAPITAL),
                _write_json(tmp, 'blogger.json', SAMPLE_BLOGGER),
            ]
            out = _run_through_main(paths, tmp)
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn('强烈买入', text)
        self.assertNotIn('保证收益', text)
        self.assertNotIn('承诺收益', text)
        self.assertNotIn('稳赚', text)

    # ------------------------------------------------------------------ #
    # 7. Output matches schema
    # ------------------------------------------------------------------ #

    def test_output_matches_schema(self):
        """Output should contain all required top-level fields from schema."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = [
                _write_json(tmp, 'quotes.json', SAMPLE_QUOTES),
                _write_json(tmp, 'capital.json', SAMPLE_CAPITAL),
            ]
            out = _run_through_main(paths, tmp)
        required = SCHEMA.get('required', [])
        for field in required:
            self.assertIn(field, out, f"Missing required field: {field}")
        # Check data > dimensions > items required fields
        dim_item_schema = (
            SCHEMA['properties']['data']['properties']['dimensions']['items']
        )
        dim_required = dim_item_schema.get('required', [])
        for dim in out['data']['dimensions']:
            for field in dim_required:
                self.assertIn(field, dim, f"Missing required dimension field: {field}")

    # ------------------------------------------------------------------ #
    # 8. Corrupt input handled gracefully
    # ------------------------------------------------------------------ #

    def test_corrupt_input_handled_gracefully(self):
        """Corrupt JSON should produce errors but not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = os.path.join(tmp, 'bad.json')
            with open(bad_path, 'w') as f:
                f.write('{corrupt json}')
            out = _run_through_main([bad_path], tmp)
        self.assertEqual(out['status'], 'failed')
        self.assertTrue(len(out['errors']) > 0)
        self.assertNotIn('Traceback', str(out['errors']))

    # ------------------------------------------------------------------ #
    # 9. Empty input produces empty status
    # ------------------------------------------------------------------ #

    def test_empty_input_status(self):
        """No input files -> status 'empty'."""
        with tempfile.TemporaryDirectory() as tmp:
            out = _run_through_main([], tmp)
        self.assertEqual(out['status'], 'empty')

    # ------------------------------------------------------------------ #
    # 10. Timestamp format
    # ------------------------------------------------------------------ #

    def test_timestamp_has_timezone_no_microseconds(self):
        """generated_at must match ISO 8601 with timezone, no microseconds."""
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            out = _run_through_main([p], tmp)
        ts = out['generated_at']
        self.assertIsNotNone(
            re.match(
                r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
            )
        )
        self.assertNotIn('.', ts)

    # ------------------------------------------------------------------ #
    # 11. Coverage rate is correct float
    # ------------------------------------------------------------------ #

    def test_coverage_rate_is_float(self):
        """coverage_rate should be a float between 0 and 1."""
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            out = _run_through_main([p], tmp)
        rate = out['data']['coverage_rate']
        self.assertIsInstance(rate, float)
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 1.0)

    # ------------------------------------------------------------------ #
    # 12. Failure conditions listed
    # ------------------------------------------------------------------ #

    def test_failure_conditions_listed(self):
        """失效条件 should be populated from opposing evidence and missing data."""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            out = _run_through_main([p1], tmp)
        self.assertIsInstance(out['data']['失效条件'], list)
        self.assertTrue(len(out['data']['失效条件']) > 0)

    # ------------------------------------------------------------------ #
    # 13. Confidence enum string
    # ------------------------------------------------------------------ #

    def test_confidence_enum_string(self):
        """confidence must be one of 'high', 'medium', 'low'."""
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_json(tmp, 'quotes.json', SAMPLE_QUOTES)
            out = _run_through_main([p], tmp)
        self.assertIn(out['data']['confidence'], ('high', 'medium', 'low'))


if __name__ == '__main__':
    unittest.main()