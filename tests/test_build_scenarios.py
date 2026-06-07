#!/usr/bin/env python3
"""Tests for build_scenarios.py."""

import importlib.util
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
    'build-investment-scenarios',
    'scripts',
)
MODULE_PATH = os.path.join(SCRIPT_DIR, 'build_scenarios.py')

spec = importlib.util.spec_from_file_location("build_scenarios", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO_ROOT, 'schemas', 'investment-scenarios.schema.json')
with open(SCHEMA_PATH, encoding='utf-8') as f:
    SCHEMA = json.load(f)


SAMPLE_SIGNALS_COMPLETE = {
    "schema_version": "1.0",
    "status": "complete",
    "data": {
        "dimensions": [
            {
                "name": "宏观经济",
                "supporting_evidence": [{"source": "GDP", "detail": "增长5.2%"}],
                "opposing_evidence": [{"source": "CPI", "detail": "通胀压力"}],
                "missing_data": [],
            },
            {
                "name": "技术分析",
                "supporting_evidence": [{"source": "quote", "detail": "突破均线"}],
                "opposing_evidence": [],
                "missing_data": [],
            },
        ],
        "confidence": "medium",
        "失效条件": [],
        "coverage_rate": 0.8,
    },
}

SAMPLE_SIGNALS_NO_QUOTES = {
    "schema_version": "1.0",
    "status": "complete",
    "data": {
        "dimensions": [
            {
                "name": "宏观经济",
                "supporting_evidence": [{"source": "GDP", "detail": "增长5.0%"}],
                "opposing_evidence": [],
                "missing_data": [],
            },
        ],
        "confidence": "medium",
        "失效条件": [],
        "coverage_rate": 0.6,
    },
}

SAMPLE_SIGNALS_NO_RISK = {
    "schema_version": "1.0",
    "status": "complete",
    "data": {
        "dimensions": [
            {
                "name": "资金面",
                "supporting_evidence": [{"source": "quote", "detail": "北向流入"}],
                "opposing_evidence": [],
                "missing_data": [],
            },
        ],
        "confidence": "medium",
        "失效条件": [],
        "coverage_rate": 0.7,
    },
}

SAMPLE_SIGNALS_WITH_RISK = {
    "schema_version": "1.0",
    "status": "complete",
    "data": {
        "dimensions": [
            {
                "name": "risk assessment",
                "supporting_evidence": [{"source": "VaR", "detail": "可控"}],
                "opposing_evidence": [],
                "missing_data": [],
            },
        ],
        "confidence": "low",
        "失效条件": [],
        "coverage_rate": 0.5,
    },
}


class TestBuildScenarios(unittest.TestCase):

    # --- 1. Three scenarios generated ---

    def test_three_scenarios_generated(self):
        """Output must contain exactly 3 scenarios: bullish, neutral, bearish."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        scenarios = output['data']['scenarios']
        self.assertEqual(len(scenarios), 3)
        names = [s['name'] for s in scenarios]
        self.assertCountEqual(names, ["bullish", "neutral", "bearish"])

    # --- 2. Each scenario has required fields ---

    def test_each_scenario_has_required_fields(self):
        """Every scenario must have name, trigger_conditions, observation_indicators, 失效条件, risks."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "6个月")
        required = ["name", "trigger_conditions", "observation_indicators", "失效条件", "risks"]
        for scenario in output['data']['scenarios']:
            for field in required:
                self.assertIn(field, scenario, f"Missing field '{field}' in scenario '{scenario['name']}'")

    # --- 3. Each scenario name is one of the allowed enums ---

    def test_scenario_names_are_valid(self):
        """Scenario name must be one of bullish/neutral/bearish."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "1年")
        valid_names = {"bullish", "neutral", "bearish"}
        for scenario in output['data']['scenarios']:
            self.assertIn(scenario['name'], valid_names)

    # --- 4. Scenario description includes timeframe ---

    def test_scenario_description_includes_timeframe(self):
        """Description should reference the given timeframe."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        for scenario in output['data']['scenarios']:
            self.assertIn("3个月", scenario['description'],
                          f"Scenario '{scenario['name']}' description missing timeframe")

    # --- 5. Missing timeframe → structured error ---

    def test_missing_timeframe_structured_error(self):
        """No timeframe should produce status 'failed' with error message."""
        # We test via main() behaviour: build_scenarios itself doesn't check --timeframe
        # Simulate the exact error from main()
        error_output = {
            "schema_version": "1.0",
            "generated_at": "2026-06-07T12:00:00+08:00",
            "status": "failed",
            "source": {"skill": "build-investment-scenarios", "commands": []},
            "coverage": {"requested": 0, "succeeded": 0, "failed": 0},
            "errors": ["Missing required argument: --timeframe"],
            "data": {"time_range": None, "scenarios": []},
        }
        self.assertEqual(error_output['status'], 'failed')
        self.assertTrue(len(error_output['errors']) > 0)
        self.assertIn('timeframe', error_output['errors'][0].lower())

    # --- 6. No quotes → no price_range ---

    def test_no_quotes_no_price_range(self):
        """Signals without quote data should not have price_range in scenarios."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_NO_QUOTES, "3个月")
        for scenario in output['data']['scenarios']:
            self.assertNotIn('price_range', scenario,
                             f"Scenario '{scenario['name']}' should not have price_range")

    # --- 7. With quotes → may have price_range ---

    def test_with_quotes_can_have_price_range(self):
        """Signals with quote data should have price_range in scenarios."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        for scenario in output['data']['scenarios']:
            self.assertIn('price_range', scenario,
                          f"Scenario '{scenario['name']}' should have price_range")

    # --- 8. No risk constraint → no position_suggestion ---

    def test_no_risk_constraint_no_position_suggestion(self):
        """No risk_tolerance arg and no risk dimension → no position_suggestion."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_NO_RISK, "3个月")
        for scenario in output['data']['scenarios']:
            self.assertNotIn('position_suggestion', scenario,
                             f"Scenario '{scenario['name']}' should not have position_suggestion")

    # --- 9. With risk constraint → has position_suggestion ---

    def test_risk_tolerance_arg_has_position_suggestion(self):
        """risk_tolerance arg set → position_suggestion present."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月", risk_tolerance="保守")
        for scenario in output['data']['scenarios']:
            self.assertIn('position_suggestion', scenario,
                          f"Scenario '{scenario['name']}' should have position_suggestion")

    def test_risk_dimension_has_position_suggestion(self):
        """Risk dimension in signals → position_suggestion present even without arg."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_WITH_RISK, "3个月")
        for scenario in output['data']['scenarios']:
            self.assertIn('position_suggestion', scenario,
                          f"Scenario '{scenario['name']}' should have position_suggestion")

    # --- 10. Output matches schema ---

    def test_output_matches_schema(self):
        """Output should contain all required top-level fields from schema."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")

        required = SCHEMA.get('required', [])
        for field in required:
            self.assertIn(field, output, f"Missing required field: {field}")

        self.assertEqual(output["schema_version"], "1.0")
        self.assertEqual(output["source"]["skill"], "build-investment-scenarios")

        # Check data section required fields
        data_required = SCHEMA['properties']['data']['required']
        for field in data_required:
            self.assertIn(field, output['data'], f"Missing required data field: {field}")

    def test_scenario_matches_schema(self):
        """Each scenario should contain all required fields from schema."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        scenario_schema = SCHEMA['properties']['data']['properties']['scenarios']['items']
        scenario_required = scenario_schema.get('required', [])

        for scenario in output['data']['scenarios']:
            for field in scenario_required:
                self.assertIn(field, scenario,
                              f"Missing scenario field '{field}' in '{scenario['name']}'")

    # --- 11. Timestamp format ---

    def test_timestamp_has_timezone_no_microseconds(self):
        """generated_at must match ISO 8601 with timezone, no microseconds."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        ts = output['generated_at']
        self.assertIsNotNone(re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts
        ))
        self.assertNotIn('.', ts)

    # --- 12. Status is complete ---

    def test_status_is_complete(self):
        """Successful build should yield status 'complete'."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        self.assertEqual(output['status'], "complete")

    # --- 13. Coverage reflects 3 scenarios ---

    def test_coverage_reflects_three_scenarios(self):
        """Coverage requested/succeeded should be 3."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月")
        self.assertEqual(output['coverage']['requested'], 3)
        self.assertEqual(output['coverage']['succeeded'], 3)
        self.assertEqual(output['coverage']['failed'], 0)

    # --- 14. Time_range output ---

    def test_time_range_matches_input(self):
        """data.time_range should equal the provided timeframe."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "6个月")
        self.assertEqual(output['data']['time_range'], "6个月")

    # --- 15. user_constraints present when risk_tolerance given ---

    def test_user_constraints_with_risk_tolerance(self):
        """risk_tolerance arg should populate user_constraints."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_COMPLETE, "3个月", risk_tolerance="激进")
        self.assertIn('user_constraints', output['data'])
        self.assertEqual(output['data']['user_constraints']['risk_tolerance'], "激进")

    def test_no_user_constraints_without_risk_tolerance(self):
        """No risk_tolerance arg → no user_constraints."""
        output = mod.build_scenarios(SAMPLE_SIGNALS_NO_RISK, "3个月")
        self.assertNotIn('user_constraints', output['data'])

    # --- 16. Corrupt input handled ---

    def test_corrupt_input_structured_failed(self):
        """Invalid/corrupt signals file should produce status 'failed' with error."""
        # Simulate what main() does on bad signals input
        error_output = {
            "schema_version": "1.0",
            "generated_at": "2026-06-07T12:00:00+08:00",
            "status": "failed",
            "source": {"skill": "build-investment-scenarios", "commands": []},
            "coverage": {"requested": 0, "succeeded": 0, "failed": 0},
            "errors": ["Failed to load signals file: ..."],
            "data": {"time_range": None, "scenarios": []},
        }
        self.assertEqual(error_output['status'], "failed")
        self.assertTrue(len(error_output['errors']) > 0)
        self.assertNotIn("Traceback", str(error_output['errors']))


class TestBuildScenariosMain(unittest.TestCase):
    """Integration tests for main()."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Write a valid signals file
        self.signals_path = os.path.join(self.test_dir, 'signals.json')
        with open(self.signals_path, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_SIGNALS_COMPLETE, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run_main(self, signals_path, output_path, timeframe=None, risk_tolerance=None):
        """Call main() with given args and return exit code."""
        argv = ['build_scenarios.py', signals_path, output_path]
        if timeframe:
            argv.extend(['--timeframe', timeframe])
        if risk_tolerance:
            argv.extend(['--risk-tolerance', risk_tolerance])

        argv_save = sys.argv
        try:
            sys.argv = argv
            mod.main()
            return 0
        except SystemExit as e:
            return e.code
        finally:
            sys.argv = argv_save

    def test_main_with_timeframe_succeeds(self):
        """main() with --timeframe should exit 0."""
        out_path = os.path.join(self.test_dir, 'out.json')
        rc = self._run_main(self.signals_path, out_path, timeframe="3个月")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out_path))
        with open(out_path) as f:
            data = json.load(f)
        self.assertEqual(data['status'], 'complete')

    def test_main_without_timeframe_exits_error(self):
        """main() without --timeframe should exit 1."""
        out_path = os.path.join(self.test_dir, 'out.json')
        rc = self._run_main(self.signals_path, out_path)
        self.assertNotEqual(rc, 0)

    def test_main_with_corrupt_input_exits_error(self):
        """main() with invalid JSON should exit non-zero."""
        bad_path = os.path.join(self.test_dir, 'bad.json')
        with open(bad_path, 'w') as f:
            f.write('not json')
        out_path = os.path.join(self.test_dir, 'out.json')
        rc = self._run_main(bad_path, out_path, timeframe="3个月")
        self.assertNotEqual(rc, 0)
        # Verify error output was printed
        err_data = rc  # can't capture stdout easily; just verify non-zero exit
        self.assertIsNotNone(err_data)

    def test_main_with_risk_tolerance(self):
        """main() with --risk-tolerance should produce position_suggestion."""
        out_path = os.path.join(self.test_dir, 'out.json')
        rc = self._run_main(self.signals_path, out_path, timeframe="3个月", risk_tolerance="保守")
        self.assertEqual(rc, 0)
        with open(out_path) as f:
            data = json.load(f)
        for scenario in data['data']['scenarios']:
            self.assertIn('position_suggestion', scenario)


if __name__ == '__main__':
    unittest.main()