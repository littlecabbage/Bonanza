#!/usr/bin/env python3
"""Analyze investment signals from multi-dimension data sources.

Usage: python3 analyze_signals.py [overview.json] [quotes.json] [capital.json]
       [blogger.json] [sentiment.json] [news.json] [output.json]

All arguments except output path are optional. The script reads available
files and produces a structured signal analysis.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta


# ---- Schema constants ----

SCHEMA_VERSION = "1.0"
SKILL_NAME = "analyze-investment-signals"
DIMENSION_NAMES = ["price", "capital", "sentiment", "event"]
CST = timezone(timedelta(hours=8))


def normalize_generated_at() -> str:
    """Return ISO 8601 timestamp with timezone (+08:00), no microseconds."""
    ts = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S%z")
    return _fix_timezone(ts)


def _fix_timezone(ts: str) -> str:
    """Insert colon in timezone offset if missing (+0800 -> +08:00)."""
    if len(ts) >= 5 and ts[-5] in ("+", "-"):
        return ts[:-2] + ":" + ts[-2:]
    return ts


def load_json_file(path: str):
    """Load a JSON file, returning (data, error_or_None)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"文件不存在: {path}"
    except json.JSONDecodeError as e:
        return None, f"JSON解析错误: {e}"
    except Exception as e:
        return None, f"读取失败: {e}"


def _get_safe(data, *keys, default=None):
    """Safely traverse nested dicts."""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


# ---- Dimension analyzers ----


def analyze_price(data: dict) -> dict:
    """Analyze price dimension from stock-quotes.json data."""
    supporting = []
    opposing = []
    missing = []

    if data is None:
        return {
            "name": "price",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": ["行情数据"],
            "conclusion": "无行情数据",
        }

    quotes = _get_safe(data, "data", "quotes", default=[])
    if not quotes:
        missing.append("行情数据")
        return {
            "name": "price",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": missing,
            "conclusion": "无行情数据",
        }

    for q in quotes:
        name = q.get("name", q.get("code", "未知"))
        change_pct = q.get("change_percent") or q.get("changePercent")
        price = q.get("price")
        volume = q.get("volume")

        if change_pct is not None:
            if change_pct > 0:
                supporting.append({
                    "source": name,
                    "indicator": "涨幅",
                    "value": f"{change_pct:+.2f}%",
                    "note": "价格上涨",
                })
            elif change_pct < 0:
                opposing.append({
                    "source": name,
                    "indicator": "跌幅",
                    "value": f"{change_pct:+.2f}%",
                    "note": "价格下跌",
                })

        if price is not None and volume is not None and volume > 0:
            supporting.append({
                "source": name,
                "indicator": "成交量",
                "value": str(volume),
                "note": "有交易数据",
            })
        elif price is not None and (volume is None or volume == 0):
            opposing.append({
                "source": name,
                "indicator": "成交量",
                "value": "0",
                "note": "无成交量",
            })

    conclusion = _build_conclusion(supporting, opposing, "价格")
    return {
        "name": "price",
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "missing_data": missing,
        "conclusion": conclusion,
    }


def analyze_capital(data: dict) -> dict:
    """Analyze capital dimension from capital-movements.json data."""
    supporting = []
    opposing = []
    missing = []

    if data is None:
        return {
            "name": "capital",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": ["资金流向数据"],
            "conclusion": "无资金数据",
        }

    movements = _get_safe(data, "data", "movements", default=[])
    if not movements:
        movements = _get_safe(data, "data", "capital_flows", default=[])
    if not movements:
        missing.append("资金流向记录")
        return {
            "name": "capital",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": missing,
            "conclusion": "无资金数据",
        }

    for m in movements:
        source = m.get("name", m.get("source", "未知"))
        net = m.get("net_amount") or m.get("net_inflow")
        direction = m.get("direction")

        if net is not None:
            if net > 0:
                supporting.append({
                    "source": source,
                    "indicator": "净流入",
                    "value": str(net),
                    "note": "资金净流入",
                })
            elif net < 0:
                opposing.append({
                    "source": source,
                    "indicator": "净流出",
                    "value": str(net),
                    "note": "资金净流出",
                })

        if direction == "in":
            supporting.append({
                "source": source,
                "indicator": "方向",
                "value": "流入",
                "note": "资金流向积极",
            })
        elif direction == "out":
            opposing.append({
                "source": source,
                "indicator": "方向",
                "value": "流出",
                "note": "资金流向消极",
            })

    conclusion = _build_conclusion(supporting, opposing, "资金")
    return {
        "name": "capital",
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "missing_data": missing,
        "conclusion": conclusion,
    }


def analyze_sentiment(data: dict) -> dict:
    """Analyze sentiment dimension from blogger-updates / market-sentiment."""
    supporting = []
    opposing = []
    missing = []

    if data is None:
        return {
            "name": "sentiment",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": ["市场情绪数据"],
            "conclusion": "无情绪数据",
        }

    # Try blogger-updates format
    bloggers = _get_safe(data, "data", "bloggers", default=[])
    if bloggers:
        for b in bloggers:
            username = b.get("username", "未知博主")
            sentiment_label = b.get("sentiment") or b.get("overall_sentiment")
            if sentiment_label:
                if sentiment_label in ("positive", "bullish", "看多", "乐观"):
                    supporting.append({
                        "source": username,
                        "indicator": "情绪",
                        "value": sentiment_label,
                        "note": "博主观点积极",
                    })
                elif sentiment_label in ("negative", "bearish", "看空", "悲观"):
                    opposing.append({
                        "source": username,
                        "indicator": "情绪",
                        "value": sentiment_label,
                        "note": "博主观点消极",
                    })
        if not supporting and not opposing:
            missing.append("博主情绪标签")
    else:
        # Try market-sentiment format
        sentiment_score = _get_safe(data, "data", "sentiment_score")
        if sentiment_score is not None:
            if sentiment_score > 0:
                supporting.append({
                    "source": "市场情绪指数",
                    "indicator": "情绪分数",
                    "value": str(sentiment_score),
                    "note": "情绪偏积极",
                })
            elif sentiment_score < 0:
                opposing.append({
                    "source": "市场情绪指数",
                    "indicator": "情绪分数",
                    "value": str(sentiment_score),
                    "note": "情绪偏消极",
                })
        else:
            missing.append("情绪分数")

    conclusion = _build_conclusion(supporting, opposing, "情绪")
    return {
        "name": "sentiment",
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "missing_data": missing,
        "conclusion": conclusion,
    }


def analyze_event(data: dict) -> dict:
    """Analyze event dimension from market-news.json / market-overview.json."""
    supporting = []
    opposing = []
    missing = []

    if data is None:
        return {
            "name": "event",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": ["新闻事件数据"],
            "conclusion": "无事件数据",
        }

    # Try market-news format
    news_items = _get_safe(data, "data", "news", default=[])
    if not news_items:
        news_items = _get_safe(data, "data", "items", default=[])
    if not news_items:
        missing.append("新闻条目")
        return {
            "name": "event",
            "supporting_evidence": [],
            "opposing_evidence": [],
            "missing_data": missing,
            "conclusion": "无事件数据",
        }

    for item in news_items:
        title = item.get("title", "未知")
        sentiment_tag = item.get("sentiment") or item.get("impact")
        if sentiment_tag:
            if sentiment_tag in ("positive", "利好", "利多"):
                supporting.append({
                    "source": title[:40],
                    "indicator": "事件影响",
                    "value": "利好",
                    "note": "正面事件",
                })
            elif sentiment_tag in ("negative", "利空", "利淡"):
                opposing.append({
                    "source": title[:40],
                    "indicator": "事件影响",
                    "value": "利空",
                    "note": "负面事件",
                })

    conclusion = _build_conclusion(supporting, opposing, "事件")
    return {
        "name": "event",
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "missing_data": missing,
        "conclusion": conclusion,
    }


def _build_conclusion(supporting: list, opposing: list, label: str) -> str:
    """Build a conclusion string from evidence counts."""
    sup = len(supporting)
    opp = len(opposing)
    if sup == 0 and opp == 0:
        return f"{label}维度无有效信号"
    if sup > opp:
        return f"{label}维度偏积极（支持{sup}条 / 反对{opp}条）"
    if opp > sup:
        return f"{label}维度偏消极（支持{sup}条 / 反对{opp}条）"
    return f"{label}维度信号中性（支持{sup}条 / 反对{opp}条）"


# ---- Coverage & confidence ----


def calculate_coverage(dimensions: list) -> float:
    """Calculate coverage rate: dimensions with any evidence / total."""
    with_data = sum(
        1 for d in dimensions
        if d["supporting_evidence"] or d["opposing_evidence"]
    )
    return with_data / len(DIMENSION_NAMES)


def confidence_from_coverage(rate: float) -> str:
    """Map coverage rate to confidence enum."""
    if rate >= 0.75:
        return "high"
    if rate >= 0.50:
        return "medium"
    return "low"


def build_failure_conditions(dimensions: list) -> list:
    """Generate failure conditions from missing data and opposing evidence."""
    conditions = []
    for d in dimensions:
        if d["opposing_evidence"]:
            opposing_note = "、".join(
                e.get("note", e.get("indicator", "未知"))
                for e in d["opposing_evidence"][:3]
            )
            conditions.append(f"{d['name']}维度存在风险信号: {opposing_note}")
        if d["missing_data"]:
            labels = "、".join(d["missing_data"])
            conditions.append(f"{d['name']}维度数据缺失: {labels}")
    return conditions


# ---- Main entry point ----


def build_result(
    dimensions: list,
    errors: list,
    commands: list,
    coverage_counts: dict,
    status: str,
) -> dict:
    """Build the full output result dict matching the schema."""
    coverage_rate = calculate_coverage(dimensions)
    confidence = confidence_from_coverage(coverage_rate)
    failure_conditions = build_failure_conditions(dimensions)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": normalize_generated_at(),
        "status": status,
        "source": {
            "skill": SKILL_NAME,
            "commands": commands,
        },
        "coverage": coverage_counts,
        "errors": errors,
        "data": {
            "dimensions": dimensions,
            "confidence": confidence,
            "失效条件": failure_conditions,
            "coverage_rate": coverage_rate,
        },
    }


def detect_dimension(path: str) -> str:
    """Detect dimension from filename (case-insensitive)."""
    fname = os.path.basename(path).lower()
    if "quote" in fname:
        return "price"
    if "capital" in fname:
        return "capital"
    if "sentiment" in fname:
        return "sentiment"
    if "blogger" in fname:
        return "sentiment"
    if "news" in fname:
        return "event"
    if "overview" in fname:
        return "event"
    return "event"  # fallback


def main():
    args = sys.argv[1:]
    command = "python3 analyze_signals.py " + " ".join(args)

    # Last arg is output path if it looks like a file path
    output_path = None
    file_args = list(args)

    if len(file_args) > 0 and (
        ".json" in file_args[-1] or "/" in file_args[-1]
    ):
        output_path = file_args.pop()

    if len(file_args) == 0:
        # No input files = empty run
        result = build_result(
            dimensions=[
                {
                    "name": n,
                    "supporting_evidence": [],
                    "opposing_evidence": [],
                    "missing_data": ["未提供数据源"],
                    "conclusion": f"{n}维度无数据",
                }
                for n in DIMENSION_NAMES
            ],
            errors=[],
            commands=[command],
            coverage_counts={"requested": 0, "succeeded": 0, "failed": 0},
            status="empty",
        )
        _write_output(result, output_path)
        return

    # Map input files
    loaded = {}
    errors = []
    commands = [command]
    succeeded = 0
    failed = 0

    for i, path in enumerate(file_args):
        data, err = load_json_file(path)
        if err:
            errors.append(err)
            failed += 1
            continue
        succeeded += 1

        # Determine dimension from filename
        dim = detect_dimension(path)
        loaded[dim] = data

    # Run dimension analysis
    dimension_results = [
        analyze_price(loaded.get("price")),
        analyze_capital(loaded.get("capital")),
        analyze_sentiment(loaded.get("sentiment")),
        analyze_event(loaded.get("event")),
    ]

    # Determine status
    requested = len(file_args)
    if succeeded == 0:
        status = "failed"
    elif failed > 0:
        status = "partial"
    else:
        status = "complete"

    result = build_result(
        dimensions=dimension_results,
        errors=errors,
        commands=commands,
        coverage_counts={
            "requested": requested,
            "succeeded": succeeded,
            "failed": failed,
        },
        status=status,
    )

    _write_output(result, output_path)


def _write_output(result: dict, path: str):
    """Write result to path or stdout."""
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()