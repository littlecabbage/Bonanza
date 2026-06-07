#!/usr/bin/env python3
"""投资情景推演脚本 — 构建看多/中性/看空三情景"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_signals(path):
    """加载投资信号文件."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def has_quotes_data(signals):
    """检查信号数据中是否包含行情信息."""
    data = signals.get('data', {})
    dimensions = data.get('dimensions', [])
    for dim in dimensions:
        supporting = dim.get('supporting_evidence', [])
        opposing = dim.get('opposing_evidence', [])
        for evidence in supporting + opposing:
            if 'quote' in str(evidence).lower():
                return True
    return False


def has_risk_constraint(signals):
    """检查信号数据中是否包含风险约束信息."""
    data = signals.get('data', {})
    dimensions = data.get('dimensions', [])
    for dim in dimensions:
        if 'risk' in dim.get('name', '').lower():
            return True
    return False


def build_scenarios(signals, timeframe, risk_tolerance=None):
    """构建三种投资情景：看多、中性、看空。

    Args:
        signals: 投资信号数据
        timeframe: 时间范围（如 "3个月"）
        risk_tolerance: 风险承受能力（可选）

    Returns:
        dict: 符合 investment-scenarios schema 的输出
    """
    has_quotes = has_quotes_data(signals)
    has_risk = risk_tolerance is not None or has_risk_constraint(signals)

    scenarios = []

    # --- 看多情景 ---
    bullish = {
        "name": "bullish",
        "description": f"市场在{timeframe}内呈现上行趋势，各维度信号支持上涨",
        "trigger_conditions": [
            "宏观经济数据持续改善",
            "政策面出现利好催化",
            "资金面持续净流入",
            "技术形态突破关键阻力位",
        ],
        "observation_indicators": [
            "成交量是否持续放大",
            "北向资金流向",
            "板块轮动节奏",
            "融资余额变化",
        ],
        "失效条件": [
            "宏观经济数据低于预期",
            "政策转向收紧",
            "出现系统性风险事件",
        ],
        "risks": [
            "追高风险",
            "政策变化不及预期",
            "外部市场冲击",
        ],
    }

    # --- 中性情景 ---
    neutral = {
        "name": "neutral",
        "description": f"市场在{timeframe}内维持震荡格局，多空力量相对均衡",
        "trigger_conditions": [
            "宏观经济数据符合预期",
            "政策面保持稳定",
            "资金面中性平衡",
            "技术形态处于箱体震荡",
        ],
        "observation_indicators": [
            "成交量的异常变化",
            "关键整数关口得失",
            "市场情绪指标",
            "波动率变化",
        ],
        "失效条件": [
            "市场出现突破性行情",
            "重大政策出台打破平衡",
            "外部事件打破震荡格局",
        ],
        "risks": [
            "横盘消耗时间成本",
            "方向选择失误",
            "假突破导致的误判",
        ],
    }

    # --- 看空情景 ---
    bearish = {
        "name": "bearish",
        "description": f"市场在{timeframe}内面临下行压力，风险因素增多",
        "trigger_conditions": [
            "宏观经济数据持续走弱",
            "政策面出现收紧信号",
            "资金面持续净流出",
            "技术形态跌破关键支撑位",
        ],
        "observation_indicators": [
            "避险资产价格走势",
            "资金流出速度",
            "跌停家数变化",
            "恐慌指数变化",
        ],
        "失效条件": [
            "经济数据超预期改善",
            "政策转向宽松",
            "国家队入场维稳",
        ],
        "risks": [
            "系统性下跌风险",
            "流动性枯竭风险",
            "杠杆踩踏风险",
        ],
    }

    # 无行情数据 → 不生成价格区间
    if not has_quotes:
        # price_range 字段不设置，output 中不包含
        pass
    else:
        bullish["price_range"] = {"low": None, "high": None}
        neutral["price_range"] = {"low": None, "high": None}
        bearish["price_range"] = {"low": None, "high": None}

    # 无风险约束 → 不生成仓位建议
    if has_risk:
        bullish["position_suggestion"] = "可适当增加仓位"
        neutral["position_suggestion"] = "保持中性仓位"
        bearish["position_suggestion"] = "降低仓位控制风险"

    scenarios = [bullish, neutral, bearish]

    # 构建输出
    output = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "status": "complete",
        "source": {
            "skill": "build-investment-scenarios",
            "commands": [],
        },
        "coverage": {
            "requested": 3,
            "succeeded": 3,
            "failed": 0,
        },
        "errors": [],
        "data": {
            "time_range": timeframe,
            "scenarios": scenarios,
        },
    }

    if risk_tolerance:
        output["data"]["user_constraints"] = {
            "risk_tolerance": risk_tolerance,
        }

    return output


def main():
    parser = argparse.ArgumentParser(description="投资情景推演")
    parser.add_argument("input", help="investment-signals.json 路径")
    parser.add_argument("output", help="输出文件路径")
    parser.add_argument("--timeframe", required=False, help="时间范围（必需）")
    parser.add_argument("--risk-tolerance", help="风险承受能力（可选）")

    args = parser.parse_args()

    # 检查 timeframe
    if not args.timeframe:
        error_output = {
            "schema_version": "1.0",
            "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "status": "failed",
            "source": {
                "skill": "build-investment-scenarios",
                "commands": ["python3 build_scenarios.py " + " ".join(sys.argv[1:])],
            },
            "coverage": {
                "requested": 0,
                "succeeded": 0,
                "failed": 0,
            },
            "errors": ["Missing required argument: --timeframe"],
            "data": {
                "time_range": None,
                "scenarios": [],
            },
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 加载信号数据
    try:
        signals = load_signals(args.input)
    except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
        error_output = {
            "schema_version": "1.0",
            "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "status": "failed",
            "source": {
                "skill": "build-investment-scenarios",
                "commands": ["python3 build_scenarios.py " + " ".join(sys.argv[1:])],
            },
            "coverage": {
                "requested": 0,
                "succeeded": 0,
                "failed": 0,
            },
            "errors": [f"Failed to load signals file: {str(e)}"],
            "data": {
                "time_range": args.timeframe,
                "scenarios": [],
            },
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 构建情景
    output = build_scenarios(signals, args.timeframe, args.risk_tolerance)

    # 记录命令
    output["source"]["commands"] = ["python3 build_scenarios.py " + " ".join(sys.argv[1:])]

    # 写入输出
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Scenarios written to {args.output}")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()