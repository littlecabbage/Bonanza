#!/usr/bin/env python3
"""Inspect investment workflow run state.

Usage:
    python3 inspect_run.py <run-directory>

Reads workflow-state.json and available products, outputs:
- completed_steps
- available_products
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
        # Handle timezone offset format: 2026-06-07T10:00:00+08:00
        if '+' in dt_string or dt_string.endswith('Z'):
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        # Fallback for naive datetime
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

    # Convert to UTC for comparison
    if generated_dt.tzinfo is None:
        generated_dt = generated_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - generated_dt).total_seconds() / 3600

    return age_hours < hours_threshold


def inspect_run(run_dir):
    """Inspect run directory and return structured state."""
    run_path = Path(run_dir)

    if not run_path.exists():
        return {
            "error": f"Run directory not found: {run_dir}",
            "completed_steps": [],
            "available_products": {},
            "data_freshness": {},
            "recommended_next_steps": []
        }

    # Read workflow-state.json
    state_file = run_path / "workflow-state.json"
    workflow_state = {}
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            workflow_state = json.load(f)

    # Check available products
    product_files = [
        "blogger-updates.json",
        "market-overview.json",
        "market-sentiment.json",
        "capital-movements.json",
        "market-news.json",
        "investment-entities.json",
        "stock-quotes.json",
        "investment-signals.json",
        "investment-scenarios.json",
        "investment-report.html"
    ]

    available_products = {}
    for product in product_files:
        product_path = run_path / product
        if product_path.exists():
            if product.endswith('.json'):
                try:
                    with open(product_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        available_products[product] = {
                            "exists": True,
                            "schema_version": data.get("schema_version"),
                            "status": data.get("status"),
                            "generated_at": data.get("generated_at")
                        }
                except Exception:
                    available_products[product] = {
                        "exists": True,
                        "schema_version": None,
                        "status": None,
                        "generated_at": None
                    }
            else:
                # HTML or other files
                available_products[product] = {
                    "exists": True,
                    "schema_version": None,
                    "status": None,
                    "generated_at": None
                }

    # Calculate data freshness
    data_freshness = {}
    for product, info in available_products.items():
        if info.get("generated_at"):
            is_fresh = check_freshness(info["generated_at"])
            data_freshness[product] = {
                "generated_at": info["generated_at"],
                "is_fresh": is_fresh
            }

    # Determine completed steps from workflow state
    completed_steps = []
    if "steps" in workflow_state:
        for step in workflow_state["steps"]:
            if step.get("status") == "completed":
                completed_steps.append(step.get("skill"))

    # Also infer from available products
    product_to_skill = {
        "blogger-updates.json": "collect-blogger-updates",
        "market-overview.json": "collect-market-overview",
        "market-sentiment.json": "collect-market-sentiment",
        "capital-movements.json": "collect-capital-movements",
        "market-news.json": "collect-market-news",
        "investment-entities.json": "extract-investment-entities",
        "stock-quotes.json": "fetch-stock-quotes",
        "investment-signals.json": "analyze-investment-signals",
        "investment-scenarios.json": "build-investment-scenarios",
        "investment-report.html": "render-investment-report"
    }

    for product in available_products:
        skill = product_to_skill.get(product)
        if skill and skill not in completed_steps:
            completed_steps.append(skill)

    # Recommend next steps
    recommended_next = []

    # Priority order for recommendations
    if "collect-market-overview" not in completed_steps:
        recommended_next.append({
            "skill": "collect-market-overview",
            "reason": "市场概览是分析的基础数据",
            "expected_output": "market-overview.json"
        })

    if "collect-blogger-updates" not in completed_steps:
        recommended_next.append({
            "skill": "collect-blogger-updates",
            "reason": "博主观点提供市场情绪和趋势",
            "expected_output": "blogger-updates.json"
        })

    if "collect-market-sentiment" not in completed_steps:
        recommended_next.append({
            "skill": "collect-market-sentiment",
            "reason": "市场情绪数据补充量化信号",
            "expected_output": "market-sentiment.json"
        })

    if "collect-capital-movements" not in completed_steps:
        recommended_next.append({
            "skill": "collect-capital-movements",
            "reason": "资金流向揭示机构动向",
            "expected_output": "capital-movements.json"
        })

    if "collect-market-news" not in completed_steps:
        recommended_next.append({
            "skill": "collect-market-news",
            "reason": "新闻快讯提供事件驱动因素",
            "expected_output": "market-news.json"
        })

    if "extract-investment-entities" not in completed_steps:
        if any(p in available_products for p in [
            "blogger-updates.json", "market-sentiment.json", "market-news.json"
        ]):
            recommended_next.append({
                "skill": "extract-investment-entities",
                "reason": "从文本中提取股票和板块实体",
                "expected_output": "investment-entities.json"
            })

    if "fetch-stock-quotes" not in completed_steps:
        if "investment-entities.json" in available_products:
            recommended_next.append({
                "skill": "fetch-stock-quotes",
                "reason": "查询识别出的股票实时行情",
                "expected_output": "stock-quotes.json"
            })

    if "analyze-investment-signals" not in completed_steps:
        if any(p in available_products for p in [
            "market-overview.json", "stock-quotes.json", "capital-movements.json"
        ]):
            recommended_next.append({
                "skill": "analyze-investment-signals",
                "reason": "综合分析多维度信号",
                "expected_output": "investment-signals.json"
            })

    if "build-investment-scenarios" not in completed_steps:
        if "investment-signals.json" in available_products:
            recommended_next.append({
                "skill": "build-investment-scenarios",
                "reason": "构建多情景投资分析（可选）",
                "expected_output": "investment-scenarios.json"
            })

    if "render-investment-report" not in completed_steps:
        if "investment-signals.json" in available_products:
            recommended_next.append({
                "skill": "render-investment-report",
                "reason": "生成最终 HTML 报告",
                "expected_output": "investment-report.html"
            })

    # Limit to top 3 recommendations
    recommended_next = recommended_next[:3]

    return {
        "run_directory": str(run_path.absolute()),
        "completed_steps": completed_steps,
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
