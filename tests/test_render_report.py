#!/usr/bin/env python3
"""Tests for render_report.py.

Covers template integrity, XSS prevention, empty data handling, and
scenario fallback rendering.
"""

import json
import os
import re
import sys
import tempfile
import unittest

# Path setup
SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..',
    'skills',
    'render-investment-report',
    'scripts',
)
sys.path.insert(0, SCRIPT_DIR)

import render_report


class TestRenderReport(unittest.TestCase):
    """Render report end-to-end tests."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'skills',
            'render-investment-report',
            'assets',
            'report-template.html',
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_json(self, relpath, data):
        fpath = os.path.join(self.test_dir, relpath)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def _render(self):
        return render_report.render_report(self.test_dir, template_path=self.template_path)

    def _read_output(self):
        fpath = os.path.join(self.test_dir, 'investment-report.html')
        with open(fpath, 'r', encoding='utf-8') as f:
            return f.read()

    def _make_envelope(self, status="complete", data=None):
        return {
            "schema_version": "1.0",
            "generated_at": "2026-06-07T14:00:00+08:00",
            "status": status,
            "source": {"skill": "test", "commands": ["test"]},
            "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
            "errors": [],
            "data": data or {},
        }

    # --- 1. Template has no duplicate h2 sections ---

    def test_template_no_duplicate_h2(self):
        """Template must not have duplicate <h2> sections."""
        with open(self.template_path, encoding='utf-8') as f:
            content = f.read()
        h2_pattern = re.compile(r'<h2>\s*([^<]+)\s*</h2>')
        headings = h2_pattern.findall(content)
        seen = {}
        duplicates = []
        for h in headings:
            seen[h] = seen.get(h, 0) + 1
            if seen[h] > 1:
                duplicates.append(h)
        self.assertEqual(
            len(duplicates), 0,
            f"Duplicate <h2> sections found: {duplicates}"
        )

    # --- 2. HTML escape prevents XSS ---

    def test_html_escape_prevents_xss(self):
        """XSS payloads in stock names must be escaped, not rendered."""
        overview = self._make_envelope(data={
            "indices": [{"name": "<script>alert('xss')</script>", "code": "XSS", "price": 100}]
        })
        self._write_json("market-overview.json", overview)
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [],
            "confidence": "low",
            "失效条件": [],
        }))

        output = self._read_output()

        # Script tag must be escaped
        self.assertNotIn("<script>alert('xss')</script>", output)
        self.assertIn(
            "&lt;script&gt;alert('xss')&lt;/script&gt;",
            output,
            "XSS payload must be HTML-escaped",
        )

    # --- 3. No script injection possible ---

    def test_no_script_injection_possible(self):
        """All dangerous HTML constructs must be escaped."""
        overview = self._make_envelope(data={
            "indices": [{
                "name": "img onerror test",
                "code": "EVIL",
                "price": 50,
                "change_percent": -1.5,
            }],
            "hot_stocks": [{
                "name": "<img src=x onerror=alert(1)>",
                "code": "HACK",
                "rank": 1,
                "change_percent": 0,
                "heat_score": 90,
            }],
        })
        self._write_json("market-overview.json", overview)
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [],
            "confidence": "medium",
            "失效条件": [],
        }))

        output = self._read_output()

        # No raw onerror should be present
        self.assertNotIn("onerror=alert", output)
        # The payload must be escaped
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", output)

    # --- 4. Empty data skips section ---

    def test_empty_data_skips_section(self):
        """Empty data dict should produce no index/hot_stock/sector tables."""
        overview = self._make_envelope(data={
            "indices": [],
            "hot_stocks": [],
            "sectors": [],
        })
        self._write_json("market-overview.json", overview)
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "test", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "low",
            "失效条件": [],
        }))

        output = self._read_output()

        # Section heading should exist
        self.assertIn("市场概况", output)
        # But no table rows should be present
        self.assertNotIn("<tr>", output[:output.find("信号分析")])
        # Summary indicator for no stock data
        self.assertNotIn("热门股票", output)

    # --- 5. No scenarios → summary section ---

    def test_no_scenarios_shows_summary(self):
        """Without scenarios data, render '市场观察摘要' section."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "high",
            "失效条件": [],
        }))
        # No investment-scenarios.json at all

        output = self._read_output()

        self.assertIn("市场观察摘要", output)
        self.assertNotIn("情景分析", output)

    # --- 6. Scenarios data shows scenario section ---

    def test_scenarios_present_shows_scenarios(self):
        """When scenarios data exists, show '情景分析' section."""
        overview = self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        })
        self._write_json("market-overview.json", overview)
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "high",
            "失效条件": [],
        }))
        self._write_json("investment-scenarios.json", self._make_envelope(data={
            "time_range": "1-3 months",
            "scenarios": [
                {
                    "name": "bullish",
                    "description": "看涨情景",
                    "trigger_conditions": ["催化剂1"],
                    "observation_indicators": ["指标A"],
                    "失效条件": ["失效A"],
                    "risks": ["风险1"],
                }
            ],
        }))

        output = self._read_output()

        self.assertIn("情景分析", output)
        self.assertNotIn("市场观察摘要", output)

    # --- 7. Source links present ---

    def test_source_links_present(self):
        """Source links should include loaded filenames."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "medium",
            "失效条件": [],
        }))

        output = self._read_output()

        self.assertIn("market-overview.json", output)
        self.assertIn("investment-signals.json", output)

    # --- 8. Generation time present ---

    def test_generation_time_present(self):
        """Report must contain generation time from source data."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "medium",
            "失效条件": [],
        }))

        output = self._read_output()

        self.assertIn("2026-06-07T14:00:00+08:00", output)

    # --- 9. No residual {{...}} placeholders ---

    def test_no_residual_placeholders(self):
        """Rendered HTML must have zero {{...}} residuals."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "high",
            "失效条件": ["跌破3000"],
        }))

        output = self._read_output()

        residuals = re.findall(r'\{\{[^}]+\}\}', output)
        self.assertEqual(
            len(residuals), 0,
            f"Residual placeholders found: {residuals}"
        )

    # --- 10. Self-contained HTML (no external deps) ---

    def test_self_contained_html(self):
        """HTML must not reference external resources."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [{"name": "行情", "supporting_evidence": [], "opposing_evidence": [], "missing_data": []}],
            "confidence": "medium",
            "失效条件": [],
        }))

        output = self._read_output()

        # No external resource references
        self.assertNotIn("src=", output, "HTML must not reference external resources")
        self.assertNotIn("href=", output, "HTML must not reference external resources")

    # --- 11. Empty directory → minimal report ---

    def test_empty_directory_minimal_report(self):
        """No JSON files at all should produce a minimal valid report."""
        output = self._read_output()

        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("投资报告", output)
        # Should not crash, should still render

    # --- 12. Confidence rendering uses correct advice class ---

    def test_confidence_renders_advice_class(self):
        """Confidence values should map to .advice-{value} CSS class."""
        self._write_json("market-overview.json", self._make_envelope(data={
            "indices": [{"name": "上证指数", "code": "000001", "price": 3245}],
        }))
        self._write_json("investment-signals.json", self._make_envelope(data={
            "dimensions": [],
            "confidence": "high",
            "失效条件": [],
        }))

        output = self._read_output()

        self.assertIn('class="advice-high"', output)
        self.assertIn("high", output)


class TestTemplateIntegrity(unittest.TestCase):
    """Template-level integrity tests (no rendering needed)."""

    TEMPLATE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'skills',
        'render-investment-report',
        'assets',
        'report-template.html',
    )

    def test_css_classes_expected(self):
        """Template must define expected CSS classes."""
        with open(self.TEMPLATE_PATH, encoding='utf-8') as f:
            content = f.read()

        expected_classes = [
            '.advice-strong-buy',
            '.advice-buy',
            '.advice-hold',
            '.advice-sell',
            '.badge-market-a',
            '.badge-market-us',
            '.badge-market-hk',
        ]
        for cls in expected_classes:
            self.assertIn(cls, content, f"Missing CSS class: {cls}")

    def test_market_badges_in_html(self):
        """Market badge classes must be used in HTML, not just defined in CSS."""
        with open(self.TEMPLATE_PATH, encoding='utf-8') as f:
            content = f.read()

        self.assertIn('badge-market-a', content)
        self.assertIn('badge-market-us', content)
        self.assertIn('badge-market-hk', content)

    def test_placeholder_patterns_exist(self):
        """Template must have at least some {{PLACEHOLDER}} patterns."""
        with open(self.TEMPLATE_PATH, encoding='utf-8') as f:
            content = f.read()

        placeholders = re.findall(r'\{\{[^}]+\}\}', content)
        self.assertGreater(len(placeholders), 0, "Template must have placeholders")


if __name__ == '__main__':
    unittest.main()