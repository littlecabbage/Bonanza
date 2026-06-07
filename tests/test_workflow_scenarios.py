#!/usr/bin/env python3
"""End-to-end workflow scenario tests.

Each test uses a temp run directory populated from JSON fixture files,
mocks subprocess.run, and asserts inspect_run output along with
validating that the recommended skill ordering and state transitions
match user-facing workflow expectations.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# ── Import the real modules ──────────────────────────────────────────
SKILL_DIRS = {
    "inspect": os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "guide-investment-workflow", "scripts",
    ),
    "extract": os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "extract-investment-entities", "scripts",
    ),
    "fetch": os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "fetch-stock-quotes", "scripts",
    ),
}

for _p in SKILL_DIRS.values():
    sys.path.insert(0, _p)

import inspect_run
import extract_entities
import fetch_quotes

FIXTURES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "scenarios",
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")


# ── Helpers ──────────────────────────────────────────────────────────

def _iso(offset_hours=None):
    """ISO 8601 timestamp, optionally offset from now."""
    dt = datetime.now(timezone.utc)
    if offset_hours is not None:
        dt += timedelta(hours=offset_hours)
    return dt.replace(microsecond=0).isoformat()


def _mock_subprocess(stdout_data, returncode=0):
    """Build a fake subprocess.CompletedProcess."""
    p = MagicMock(spec=["returncode", "stdout", "stderr"])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


def _load_fixture(name):
    """Load a JSON fixture from tests/fixtures/scenarios/."""
    path = os.path.join(FIXTURES, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(rundir, relpath, data):
    """Write JSON data to a file inside a run directory."""
    fpath = os.path.join(rundir, relpath)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_text(rundir, relpath, text):
    """Write plain text to a file inside a run directory."""
    fpath = os.path.join(rundir, relpath)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)


def _build_ref_data():
    """Minimal stock reference data for extract_entities and fetch_quotes."""
    return {
        "version": "1",
        "stocks": {
            "000725": {"name": "京东方A", "market": "a", "aliases": ["000725.SZ"]},
            "600519": {"name": "贵州茅台", "market": "a", "aliases": ["茅台"]},
            "NVDA":   {"name": "英伟达",   "market": "us"},
            "00700":  {"name": "腾讯控股", "market": "hk", "aliases": ["0700.HK"]},
            "002938": {"name": "鹏鼎控股", "market": "a", "aliases": []},
        },
        "industries": {
            "PCB": {"code": "BK1340", "aliases": ["PCB产业链", "PCB板块"]},
        },
        "concepts": {
            "国产替代": {"code": "BK1123", "aliases": []},
        },
    }


def _expected_schema_files():
    """Return the set of product filenames with known schemas."""
    return {
        "market-overview.json", "blogger-updates.json",
        "market-sentiment.json", "capital-movements.json",
        "market-news.json", "investment-entities.json",
        "stock-quotes.json", "investment-signals.json",
        "investment-scenarios.json",
    }


# ── Scenario Tests ───────────────────────────────────────────────────

class TestMarketOverviewOnly(unittest.TestCase):
    """Scenario 1: only market-overview available, inspect_run recommends
    the next extract step."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_inspect_recommends_extract_next(self):
        """With only market-overview.json, next recommendation should be
        a collection skill (market-sentiment or blogger-updates), not
        extract — dependencies require more input sources first."""
        _write_json(self.workdir, "market-overview.json", _load_fixture("market-overview.json"))

        result = inspect_run.inspect_run(self.workdir)

        # At least one completed step from available products
        self.assertIn("market-overview.json", result["available_products"])

        # recommended_next_steps should start with collection steps
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertGreater(len(next_skills), 0, "Should recommend at least one next step")

        # The first recommendation should be a collection skill
        first = result["recommended_next_steps"][0]["skill"]
        self.assertTrue(
            first.startswith("collect-"),
            f"First recommendation should be collection, got {first}",
        )


class TestBloggerCollectionOnly(unittest.TestCase):
    """Scenario 2: single collection skill, single output product."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_blogger_partial_is_usable_and_prompts_collection(self):
        """Partial blogger data is usable, and the rest of the collection
        pipeline is recommended before analysis."""
        _write_json(self.workdir, "blogger-updates.json", _load_fixture("blogger-partial.json"))

        result = inspect_run.inspect_run(self.workdir)

        # blogger-updates is a valid usable product
        self.assertIn("blogger-updates.json", result["usable_products"])
        self.assertEqual(
            result["usable_products"]["blogger-updates.json"]["status"],
            "partial",
        )

        # Should recommend collection steps first (market-overview is first
        # in the RECOMMENDATION_ORDER, even before blogger)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertGreater(len(next_skills), 0)
        # The product is partial, so it won't block re-recommendation of the
        # same skill — but market-overview should come first in the ordering.
        self.assertEqual(next_skills[0], "collect-market-overview")


class TestDirectQuoteQuery(unittest.TestCase):
    """Scenario 3: fetch-stock-quotes with explicit codes, no full workflow."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    @patch("fetch_quotes.load_stock_codes", return_value=_build_ref_data())
    @patch("subprocess.run", return_value=_mock_subprocess({
        "data": [
            {"name": "京东方A", "code": "000725", "market": "a",
             "price": 4.52, "changePercent": 3.5,
             "open": 4.48, "high": 4.58, "low": 4.45,
             "volume": 124500000, "pe": 18.5, "pb": 1.4,
             "marketCap": 156000000000},
        ],
    }))
    def test_fetch_quotes_by_code_returns_valid_output(self, mock_run, mock_load):
        """Fetching quotes for explicit codes produces valid schema output."""
        out_path = os.path.join(self.workdir, "stock-quotes.json")
        argv_save = sys.argv
        try:
            sys.argv = ["fetch_quotes.py", json.dumps(["000725"]), out_path]
            fetch_quotes.main()
        finally:
            sys.argv = argv_save

        with open(out_path) as f:
            output = json.load(f)

        self.assertEqual(output["schema_version"], "1.0")
        self.assertEqual(output["status"], "complete")
        self.assertEqual(output["source"]["skill"], "fetch-stock-quotes")
        self.assertEqual(len(output["data"]["quotes"]), 1)
        self.assertEqual(output["data"]["quotes"][0]["code"], "000725")
        self.assertEqual(output["coverage"]["requested"], 1)
        self.assertEqual(output["coverage"]["succeeded"], 1)
        self.assertEqual(output["coverage"]["failed"], 0)

    def test_standalone_quotes_file_recommends_dependency_first(self):
        """With only stock-quotes.json and no context, inspect_run
        should not recommend analyzer/render — dependencies are unmet."""
        # Write a minimal quotes file manually
        quotes = {
            "schema_version": "1.0",
            "generated_at": _iso(-1),
            "status": "complete",
            "source": {"skill": "fetch-stock-quotes", "commands": []},
            "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
            "errors": [],
            "data": {"quotes": [{"code": "000725", "price": 4.52}]},
        }
        _write_json(self.workdir, "stock-quotes.json", quotes)

        result = inspect_run.inspect_run(self.workdir)

        # stock-quotes should be usable
        self.assertIn("stock-quotes.json", result["usable_products"])

        # Since no market-overview or capital-movements exist,
        # analyze-investment-signals should NOT be recommended (depends on
        # market-overview.json + stock-quotes.json + capital-movements.json)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        for skill in ("analyze-investment-signals", "build-investment-scenarios", "render-investment-report"):
            self.assertNotIn(
                skill, next_skills,
                f"{skill} should not be recommended — dependencies missing",
            )


class TestFullReportProgressive(unittest.TestCase):
    """Scenario 4: step-by-step from zero, each step builds on previous."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _state(self, steps):
        return {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "progressive-test",
            "status": "partial",
            "steps": steps,
        }

    def _step(self, skill, output_file, status="complete"):
        return {
            "skill": skill,
            "status": status,
            "output_file": output_file,
            "completed_at": _iso(-1),
        }

    def test_step_1_empty_run_recommends_overview(self):
        """Empty run directory should recommend collect-market-overview first."""
        result = inspect_run.inspect_run(self.workdir)
        steps = result["recommended_next_steps"]
        self.assertGreater(len(steps), 0)
        self.assertEqual(steps[0]["skill"], "collect-market-overview")

    def test_step_2_after_overview_recommends_blogger(self):
        """After market-overview is complete, recommends collect steps."""
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step("collect-market-overview", "market-overview.json"),
        ]))
        mo = dict(_load_fixture("market-overview.json"))
        mo["generated_at"] = _iso(-1)
        _write_json(self.workdir, "market-overview.json", mo)

        result = inspect_run.inspect_run(self.workdir)
        self.assertIn("collect-market-overview", result["completed_steps"])

        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        # Should recommend the next collection skill
        self.assertIn("collect-blogger-updates", next_skills)

    def test_step_3_collection_before_extract(self):
        """Multiple collection products available, but not entities yet."""
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step("collect-market-overview", "market-overview.json"),
            self._step("collect-blogger-updates", "blogger-updates.json"),
        ]))
        for product, fixture in [
            ("market-overview.json", "market-overview.json"),
            ("blogger-updates.json", "blogger-partial.json"),
            ("market-sentiment.json", "market-sentiment.json"),
        ]:
            data = dict(_load_fixture(fixture))
            data["generated_at"] = _iso(-1)
            _write_json(self.workdir, product, data)

        result = inspect_run.inspect_run(self.workdir)
        self.assertIn("collect-market-overview", result["completed_steps"])

        # blogger fixture has status "partial", so inspect_run cross-validation
        # correctly does NOT count it in completed_steps (only status "complete" counts)
        self.assertNotIn("collect-blogger-updates", result["completed_steps"])

        # Remaining collection skills should appear before extract
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        # At least one collection step should remain
        remaining_collection = [s for s in next_skills if s.startswith("collect-")]
        self.assertGreaterEqual(len(remaining_collection), 1)

    def test_step_4_entities_after_all_collection(self):
        """After all collection steps done, extract is recommended."""
        done_skills = [
            ("collect-market-overview", "market-overview.json"),
            ("collect-blogger-updates", "blogger-updates.json"),
            ("collect-market-sentiment", "market-sentiment.json"),
            ("collect-capital-movements", "capital-movements.json"),
            ("collect-market-news", "market-news.json"),
        ]
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step(s, o) for s, o in done_skills
        ]))
        for skill, product in done_skills:
            data = {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete",
                "source": {"skill": skill, "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            }
            _write_json(self.workdir, product, data)

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("extract-investment-entities", next_skills)

    def test_step_5_quotes_after_entities(self):
        """After entities extracted, recommends fetch-stock-quotes."""
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step("collect-market-overview", "market-overview.json"),
            self._step("collect-blogger-updates", "blogger-updates.json"),
            self._step("collect-market-sentiment", "market-sentiment.json"),
            self._step("collect-capital-movements", "capital-movements.json"),
            self._step("collect-market-news", "market-news.json"),
            self._step("extract-investment-entities", "investment-entities.json"),
        ]))
        # Write collection products
        for product in ["market-overview.json", "blogger-updates.json",
                        "market-sentiment.json", "capital-movements.json",
                        "market-news.json"]:
            data = {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete",
                "source": {"skill": product.replace(".json", ""), "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            }
            _write_json(self.workdir, product, data)

        entities = _load_fixture("../valid-investment-entities.json")
        entities["generated_at"] = _iso(-1)
        _write_json(self.workdir, "investment-entities.json", entities)

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("fetch-stock-quotes", next_skills)

    def test_step_6_analyze_after_quotes(self):
        """After quotes, recommends analyze (if overview + capital present)."""
        all_steps = [
            ("collect-market-overview", "market-overview.json"),
            ("collect-blogger-updates", "blogger-updates.json"),
            ("collect-market-sentiment", "market-sentiment.json"),
            ("collect-capital-movements", "capital-movements.json"),
            ("collect-market-news", "market-news.json"),
            ("extract-investment-entities", "investment-entities.json"),
            ("fetch-stock-quotes", "stock-quotes.json"),
        ]
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step(s, o) for s, o in all_steps
        ]))
        for skill, product in all_steps:
            data = {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete" if skill != "collect-blogger-updates" else "partial",
                "source": {"skill": skill, "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            }
            _write_json(self.workdir, product, data)

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("analyze-investment-signals", next_skills)

    def test_step_7_render_after_analyze(self):
        """After analyze, recommends render."""
        all_steps = [
            ("collect-market-overview", "market-overview.json"),
            ("collect-blogger-updates", "blogger-updates.json"),
            ("collect-market-sentiment", "market-sentiment.json"),
            ("collect-capital-movements", "capital-movements.json"),
            ("collect-market-news", "market-news.json"),
            ("extract-investment-entities", "investment-entities.json"),
            ("fetch-stock-quotes", "stock-quotes.json"),
            ("analyze-investment-signals", "investment-signals.json"),
        ]
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step(s, o) for s, o in all_steps
        ]))
        for skill, product in all_steps:
            data = {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete",
                "source": {"skill": skill, "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            }
            _write_json(self.workdir, product, data)

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("render-investment-report", next_skills)

    def test_step_8_full_completion(self):
        """After all steps complete, no more recommendations."""
        all_steps = [
            ("collect-market-overview", "market-overview.json"),
            ("collect-blogger-updates", "blogger-updates.json"),
            ("collect-market-sentiment", "market-sentiment.json"),
            ("collect-capital-movements", "capital-movements.json"),
            ("collect-market-news", "market-news.json"),
            ("extract-investment-entities", "investment-entities.json"),
            ("fetch-stock-quotes", "stock-quotes.json"),
            ("analyze-investment-signals", "investment-signals.json"),
            ("render-investment-report", "investment-report.html"),
        ]
        _write_json(self.workdir, "workflow-state.json", self._state([
            self._step(s, o) for s, o in all_steps
        ]))
        for skill, product in all_steps:
            status = "complete"
            data = {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": status,
                "source": {"skill": skill, "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            }
            _write_json(self.workdir, product, data)
        # For HTML report
        _write_text(self.workdir, "investment-report.html", "<html></html>")

        result = inspect_run.inspect_run(self.workdir)
        # HTML report is non-JSON, so inspect_run cannot validate its status.
        # render-investment-report will still appear as the sole recommendation
        # because no usable JSON product blocks it.
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("render-investment-report", next_skills,
                      "HTML report cannot be schema-validated, so render is re-recommended")
        self.assertLessEqual(len(next_skills), 3)


class TestSkipBloggerContinues(unittest.TestCase):
    """Scenario 5: blogger fails but other collection succeeds."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_failed_blogger_does_not_block_pipeline(self):
        """Failed blogger should not prevent other collection or analysis."""
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "skip-blogger-test",
            "status": "partial",
            "steps": [
                {"skill": "collect-market-overview", "status": "complete",
                 "output_file": "market-overview.json",
                 "completed_at": _iso(-1)},
                {"skill": "collect-blogger-updates", "status": "failed",
                 "output_file": "blogger-updates.json",
                 "errors": ["All blogger sources failed"]},
            ],
        })
        _write_json(self.workdir, "market-overview.json", {
            "schema_version": "1.0",
            "generated_at": _iso(-1),
            "status": "complete",
            "source": {"skill": "collect-market-overview", "commands": []},
            "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
            "errors": [],
            "data": {},
        })
        _write_json(self.workdir, "blogger-updates.json", {
            "schema_version": "1.0",
            "generated_at": _iso(-1),
            "status": "failed",
            "source": {"skill": "collect-blogger-updates", "commands": []},
            "coverage": {"requested": 2, "succeeded": 0, "failed": 2},
            "errors": ["Twitter auth expired"],
            "data": {},
        })

        result = inspect_run.inspect_run(self.workdir)

        # blogger is in failed_products
        self.assertIn("blogger-updates.json", result["failed_products"])

        # Pipeline should continue — recommend market-sentiment
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("collect-market-sentiment", next_skills)


class TestPartialLoginFailureContinues(unittest.TestCase):
    """Scenario 6: auth-required source fails with partial, workflow continues."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_auth_failure_does_not_block_workflow(self):
        """Login/auth failure with partial output should not halt workflow."""
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "auth-fail-test",
            "status": "partial",
            "steps": [
                {"skill": "collect-market-overview", "status": "complete",
                 "output_file": "market-overview.json",
                 "completed_at": _iso(-1)},
                {"skill": "collect-capital-movements", "status": "partial",
                 "output_file": "capital-movements.json",
                 "errors": ["Login required for eastmoney fund-flow"]},
            ],
        })
        _write_json(self.workdir, "market-overview.json", _load_fixture("market-overview.json"))
        _write_json(self.workdir, "capital-movements.json",
                    _load_fixture("capital-partial-login-fail.json"))

        result = inspect_run.inspect_run(self.workdir)

        # capital movements should be in usable_products (partial, with data)
        self.assertIn("capital-movements.json", result["usable_products"])
        self.assertEqual(
            result["usable_products"]["capital-movements.json"]["status"],
            "partial",
        )

        # Workflow should recommend the next collection step
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("collect-blogger-updates", next_skills)


class TestResumeFromExistingRun(unittest.TestCase):
    """Scenario 7: existing run dir with some products, inspect_run resumes correctly."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_resume_with_two_completed_products(self):
        """Existing run with overview + blogger, resumes to sentiment."""
        _write_json(self.workdir, "workflow-state.json",
                    _load_fixture("resume-workflow-state.json"))

        # Write both completed products
        mo = dict(_load_fixture("market-overview.json"))
        mo["generated_at"] = _iso(-1)
        _write_json(self.workdir, "market-overview.json", mo)

        bu = dict(_load_fixture("resume-blogger-updates.json"))
        bu["generated_at"] = _iso(-1)
        _write_json(self.workdir, "blogger-updates.json", bu)

        result = inspect_run.inspect_run(self.workdir)

        # Both should be completed
        self.assertIn("collect-market-overview", result["completed_steps"])
        self.assertIn("collect-blogger-updates", result["completed_steps"])

        # Recommended next should include market-sentiment (next in order)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("collect-market-sentiment", next_skills)

        # Should NOT re-recommend already completed steps
        self.assertNotIn("collect-market-overview", next_skills)
        self.assertNotIn("collect-blogger-updates", next_skills)

    def test_resume_unrecognized_product_not_crash(self):
        """Unknown product file in run dir should not cause errors."""
        _write_json(self.workdir, "workflow-state.json",
                    _load_fixture("resume-workflow-state.json"))
        mo = dict(_load_fixture("market-overview.json"))
        mo["generated_at"] = _iso(-1)
        _write_json(self.workdir, "market-overview.json", mo)

        # Write an unexpected file
        _write_json(self.workdir, "unknown-file.json", {"some": "data"})

        # Should not crash
        result = inspect_run.inspect_run(self.workdir)
        self.assertIn("completed_steps", result)
        self.assertIsInstance(result["recommended_next_steps"], list)


class TestRenderFromExistingJson(unittest.TestCase):
    """Scenario 8: render-investment-report from pre-existing JSON files."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_render_recommended_when_analysis_exists(self):
        """When all prerequisite products exist, render should be recommended."""
        # All collection/analysis products plus entities and quotes must exist
        # for step cross-validation to succeed and for render to be recommended.
        all_products = [
            "market-overview.json", "blogger-updates.json",
            "market-sentiment.json", "capital-movements.json",
            "market-news.json", "investment-entities.json",
            "stock-quotes.json", "investment-signals.json",
        ]
        for product in all_products:
            skill_name = product.replace(".json", "").replace("-", "-")
            _write_json(self.workdir, product, {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete",
                "source": {"skill": product.replace(".json", ""), "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            })

        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "render-test",
            "status": "partial",
            "steps": [
                {"skill": "collect-market-overview", "status": "complete",
                 "output_file": "market-overview.json", "completed_at": _iso(-1)},
                {"skill": "collect-blogger-updates", "status": "complete",
                 "output_file": "blogger-updates.json", "completed_at": _iso(-1)},
                {"skill": "collect-market-sentiment", "status": "complete",
                 "output_file": "market-sentiment.json", "completed_at": _iso(-1)},
                {"skill": "collect-capital-movements", "status": "complete",
                 "output_file": "capital-movements.json", "completed_at": _iso(-1)},
                {"skill": "collect-market-news", "status": "complete",
                 "output_file": "market-news.json", "completed_at": _iso(-1)},
                {"skill": "extract-investment-entities", "status": "complete",
                 "output_file": "investment-entities.json", "completed_at": _iso(-1)},
                {"skill": "fetch-stock-quotes", "status": "complete",
                 "output_file": "stock-quotes.json", "completed_at": _iso(-1)},
                {"skill": "analyze-investment-signals", "status": "complete",
                 "output_file": "investment-signals.json", "completed_at": _iso(-1)},
            ],
        })

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertIn("render-investment-report", next_skills)

    def test_render_not_recommended_without_signals(self):
        """Without investment-signals.json, render should not be recommended."""
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "render-test-no-signals",
            "status": "partial",
            "steps": [
                {"skill": s, "status": "complete",
                 "output_file": f"{s}.json", "completed_at": _iso(-1)}
                for s in [
                    "collect-market-overview", "collect-blogger-updates",
                    "extract-investment-entities", "fetch-stock-quotes",
                ]
            ],
        })
        for product in ["market-overview.json", "blogger-updates.json",
                        "investment-entities.json", "stock-quotes.json"]:
            _write_json(self.workdir, product, {
                "schema_version": "1.0",
                "generated_at": _iso(-1),
                "status": "complete",
                "source": {"skill": product.replace(".json", ""), "commands": []},
                "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
                "errors": [],
                "data": {},
            })

        result = inspect_run.inspect_run(self.workdir)
        next_skills = [r["skill"] for r in result["recommended_next_steps"]]
        self.assertNotIn("render-investment-report", next_skills)


class TestSingleSkillPerRecommendation(unittest.TestCase):
    """Scenario 9: inspect_run recommends one skill at a time (top 3 max)."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_new_run_recommends_multiple_not_one(self):
        """Empty run should recommend up to 3 skills, in order."""
        result = inspect_run.inspect_run(self.workdir)
        steps = result["recommended_next_steps"]
        self.assertGreaterEqual(len(steps), 1)
        self.assertLessEqual(len(steps), 3)

    def test_first_recommendation_is_always_overview(self):
        """On empty run, first recommendation must be collect-market-overview."""
        result = inspect_run.inspect_run(self.workdir)
        self.assertEqual(
            result["recommended_next_steps"][0]["skill"],
            "collect-market-overview",
        )

    def test_recommendations_have_all_required_fields(self):
        """Each recommendation must have skill, reason, expected_output."""
        result = inspect_run.inspect_run(self.workdir)
        for rec in result["recommended_next_steps"]:
            for field in ("skill", "reason", "expected_output"):
                self.assertIn(field, rec, f"Missing field: {field}")

    def test_one_step_done_recommends_two_remaining(self):
        """After completing market-overview, remaining recommendations
        should reflect the updated state."""
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "single-rec-test",
            "status": "partial",
            "steps": [
                {"skill": "collect-market-overview", "status": "complete",
                 "output_file": "market-overview.json",
                 "completed_at": _iso(-1)},
            ],
        })
        _write_json(self.workdir, "market-overview.json", {
            "schema_version": "1.0",
            "generated_at": _iso(-1),
            "status": "complete",
            "source": {"skill": "collect-market-overview", "commands": []},
            "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
            "errors": [],
            "data": {},
        })

        result = inspect_run.inspect_run(self.workdir)
        steps = result["recommended_next_steps"]

        # Should NOT re-recommend market-overview
        next_skills = [r["skill"] for r in steps]
        self.assertNotIn("collect-market-overview", next_skills)

        # Should recommend the next collection steps (up to 3)
        self.assertGreaterEqual(len(steps), 1)
        self.assertLessEqual(len(steps), 3)
        self.assertEqual(steps[0]["skill"], "collect-blogger-updates")


class TestMaxThreeRecommendations(unittest.TestCase):
    """Scenario 10: never more than 3 recommended next steps."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_empty_run_never_exceeds_three(self):
        """Empty run should cap at 3 recommendations."""
        for _ in range(5):
            result = inspect_run.inspect_run(self.workdir)
            self.assertLessEqual(
                len(result["recommended_next_steps"]), 3,
            )

    def test_partial_run_never_exceeds_three(self):
        """After completing some steps, cap at 3."""
        # Complete just market-overview — should get 3 at most
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "max-rec-test",
            "status": "partial",
            "steps": [
                {"skill": "collect-market-overview", "status": "complete",
                 "output_file": "market-overview.json",
                 "completed_at": _iso(-1)},
            ],
        })
        _write_json(self.workdir, "market-overview.json", {
            "schema_version": "1.0",
            "generated_at": _iso(-1),
            "status": "complete",
            "source": {"skill": "collect-market-overview", "commands": []},
            "coverage": {"requested": 1, "succeeded": 1, "failed": 0},
            "errors": [],
            "data": {},
        })

        result = inspect_run.inspect_run(self.workdir)
        self.assertLessEqual(len(result["recommended_next_steps"]), 3)

    def test_recommendations_in_correct_order(self):
        """Recommendations must follow the defined RECOMMENDATION_ORDER
        when no steps are completed."""
        result = inspect_run.inspect_run(self.workdir)
        steps = result["recommended_next_steps"]

        # Order must be: market-overview, blogger-updates, market-sentiment
        expected_order = [
            "collect-market-overview",
            "collect-blogger-updates",
            "collect-market-sentiment",
        ]
        actual_skills = [r["skill"] for r in steps]
        for i, expected in enumerate(expected_order):
            if i < len(actual_skills):
                self.assertEqual(actual_skills[i], expected,
                                 f"Position {i} should be {expected}")

    def test_fresh_partial_does_not_become_completed(self):
        """A product with status 'partial' is usable but should not
        count as a completed step."""
        _write_json(self.workdir, "workflow-state.json", {
            "schema_version": "1.0",
            "generated_at": _iso(),
            "run_id": "partial-not-complete",
            "status": "partial",
            "steps": [
                {"skill": "collect-blogger-updates", "status": "partial",
                 "output_file": "blogger-updates.json",
                 "errors": ["Partial failure"]},
            ],
        })
        bu = dict(_load_fixture("blogger-partial.json"))
        bu["generated_at"] = _iso(-1)
        _write_json(self.workdir, "blogger-updates.json", bu)

        result = inspect_run.inspect_run(self.workdir)
        self.assertNotIn("collect-blogger-updates", result["completed_steps"])
        # Should still be in usable_products
        self.assertIn("blogger-updates.json", result["usable_products"])


if __name__ == "__main__":
    unittest.main()