#!/usr/bin/env python3
"""Inspect investment workflow run state.

Usage:
    python3 inspect_run.py <run-directory>

Reads workflow-state.json and available products, outputs:
- completed_steps (status=complete AND valid JSON AND schema_version matches)
- usable_products (status=complete or partial, valid JSON, readable)
- stale_products (exists but is_fresh=False, older than 4 hours)
- failed_products (status=failed)
- invalid_products (corrupt JSON or missing schema_version)
- data_freshness
- recommended_next_steps
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_iso_datetime(dt_string):
    """Parse ISO 8601 datetime string."""
    try:
        if '+' in dt_string or dt_string.endswith('Z'):
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return datetime.fromisoformat(dt_string)
    except Exception:
        return None


def check_freshness(generated_at_string, hours_threshold=4):
    """Check if data is fresh (within hours_threshold)."""
    if not generated_at_string:
        return False

    generated_dt = parse_iso_datetime(generated_at_string)
    if not generated_dt:
        return False

    if generated_dt.tzinfo is None:
        generated_dt = generated_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - generated_dt).total_seconds() / 3600

    return age_hours < hours_threshold


def _try_load_json(path):
    """Load and validate a JSON product file.

    Returns (data, error) tuple. On success error is None.
    On failure data is None and error describes the problem.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return None, str(e)

    return data, None


PRODUCT_FILES = [
    "blogger-updates.json",
    "market-overview.json",
    "market-sentiment.json",
    "capital-movements.json",
    "market-news.json",
    "investment-entities.json",
    "stock-quotes.json",
    "investment-signals.json",
    "investment-scenarios.json",
    "investment-report.html",
]

PRODUCT_TO_SKILL = {
    "blogger-updates.json": "collect-blogger-updates",
    "market-overview.json": "collect-market-overview",
    "market-sentiment.json": "collect-market-sentiment",
    "capital-movements.json": "collect-capital-movements",
    "market-news.json": "collect-market-news",
    "investment-entities.json": "extract-investment-entities",
    "stock-quotes.json": "fetch-stock-quotes",
    "investment-signals.json": "analyze-investment-signals",
    "investment-scenarios.json": "build-investment-scenarios",
    "investment-report.html": "render-investment-report",
}

# Order for recommended_next_steps — first found not-done wins
RECOMMENDATION_ORDER = [
    ("collect-market-overview", "市场概览是分析的基础数据", "market-overview.json", None),
    ("collect-blogger-updates", "博主观点提供市场情绪和趋势", "blogger-updates.json", None),
    ("collect-market-sentiment", "市场情绪数据补充量化信号", "market-sentiment.json", None),
    ("collect-capital-movements", "资金流向揭示机构动向", "capital-movements.json", None),
    ("collect-market-news", "新闻快讯提供事件驱动因素", "market-news.json", None),
    ("extract-investment-entities", "从文本中提取股票和板块实体", "investment-entities.json", {
        "blogger-updates.json", "market-sentiment.json", "market-news.json"
    }),
    ("fetch-stock-quotes", "查询识别出的股票实时行情", "stock-quotes.json", {
        "investment-entities.json"
    }),
    ("analyze-investment-signals", "综合分析多维度信号", "investment-signals.json", {
        "market-overview.json", "stock-quotes.json", "capital-movements.json"
    }),
    ("build-investment-scenarios", "构建多情景投资分析（可选）", "investment-scenarios.json", {
        "investment-signals.json"
    }),
    ("render-investment-report", "生成最终 HTML 报告", "investment-report.html", {
        "investment-signals.json"
    }),
]


def inspect_run(run_dir):
    """Inspect run directory and return structured state."""
    run_path = Path(run_dir)

    if not run_path.exists():
        return {
            "error": f"Run directory not found: {run_dir}",
            "completed_steps": [],
            "usable_products": {},
            "stale_products": [],
            "failed_products": [],
            "invalid_products": [],
            "available_products": {},
            "data_freshness": {},
            "recommended_next_steps": []
        }

    # Read workflow-state.json (gracefully handle corruption)
    state_file = run_path / "workflow-state.json"
    workflow_state = {}
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                workflow_state = json.load(f)
        except (json.JSONDecodeError, OSError):
            workflow_state = {}

    # Categorize products
    available_products = {}
    usable_products = {}
    stale_products = []
    failed_products = []
    invalid_products = []

    for product in PRODUCT_FILES:
        product_path = run_path / product
        if not product_path.exists():
            continue

        if not product.endswith('.json'):
            # Non-JSON (HTML report) — just note it exists
            info = {
                "exists": True,
                "schema_version": None,
                "status": None,
                "generated_at": None,
            }
            available_products[product] = info
            continue

        data, load_err = _try_load_json(product_path)
        if load_err:
            # Corrupt JSON
            info = {
                "exists": True,
                "schema_version": None,
                "status": None,
                "generated_at": None,
                "error": load_err,
            }
            available_products[product] = info
            invalid_products.append(product)
            continue

        schema_version = data.get("schema_version")
        status = data.get("status")
        generated_at = data.get("generated_at")
        is_valid_schema = schema_version == "1.0"

        info = {
            "exists": True,
            "schema_version": schema_version,
            "status": status,
            "generated_at": generated_at,
        }
        if not is_valid_schema:
            info["error"] = f"Unknown schema_version: {schema_version}"
        available_products[product] = info

        # Handle HTML reports as a special case
        if product == "investment-report.html":
            continue

        # Invalid (missing/corrupt schema)
        if not is_valid_schema:
            invalid_products.append(product)
            continue

        # failed
        if status == "failed":
            failed_products.append(product)
            continue

        # usable — complete or partial, valid JSON, readable
        if status in ("complete", "partial"):
            usable_products[product] = info

            # stale check
            if not check_freshness(generated_at):
                stale_products.append(product)

    # Determine completed_steps from workflow state only
    # Only count as completed if the product is fresh (not stale)
    completed_steps = []
    if "steps" in workflow_state:
        for step in workflow_state["steps"]:
            if step.get("status") == "complete":
                skill = step.get("skill")
                output_file = step.get("output_file", "")
                # Cross-validate: product must be valid, fresh, and complete
                if skill and skill not in completed_steps:
                    product_info = available_products.get(output_file, {})
                    if product_info.get("status") == "complete" and \
                       product_info.get("schema_version") == "1.0":
                        # Check freshness — stale products are not "completed"
                        generated_at = product_info.get("generated_at")
                        if check_freshness(generated_at):
                            completed_steps.append(skill)

    # Calculate data freshness
    data_freshness = {}
    for product, info in available_products.items():
        if info.get("generated_at"):
            is_fresh = check_freshness(info["generated_at"])
            data_freshness[product] = {
                "generated_at": info["generated_at"],
                "is_fresh": is_fresh,
            }

    # Recommend next steps — skip fresh-completed steps, include stale ones
    recommended_next = []

    # Build set of "blocked" skill names: steps that are fresh-complete
    # (so they won't be re-recommended)
    fresh_completed = set(completed_steps)
    # Also consider a step "blocked from recommendation" if it's fresh and
    # its product is in usable_products (either complete or partial)
    for product, info in usable_products.items():
        skill = PRODUCT_TO_SKILL.get(product)
        if skill and check_freshness(info.get("generated_at")):
            fresh_completed.add(skill)

    for skill, reason, output_file, depends_on in RECOMMENDATION_ORDER:
        if len(recommended_next) >= 3:
            break

        # Skip if already fresh-complete or fresh-usable
        if skill in fresh_completed:
            continue

        # Check dependencies
        if depends_on:
            if not any(dep in available_products for dep in depends_on):
                continue

        recommended_next.append({
            "skill": skill,
            "reason": reason,
            "expected_output": output_file,
        })

    return {
        "run_directory": str(run_path.absolute()),
        "completed_steps": completed_steps,
        "usable_products": usable_products,
        "stale_products": stale_products,
        "failed_products": failed_products,
        "invalid_products": invalid_products,
        "available_products": available_products,
        "data_freshness": data_freshness,
        "recommended_next_steps": recommended_next,
        "workflow_state": workflow_state
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 inspect_run.py <run-directory>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]
    result = inspect_run(run_dir)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
