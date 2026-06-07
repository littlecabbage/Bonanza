#!/usr/bin/env python3
"""股票行情获取脚本"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def load_stock_codes(ref_path):
    """加载股票代码映射表"""
    with open(ref_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def classify_stocks(stocks, ref_data):
    """将股票代码按市场分类，同时识别未知代码."""
    classified = {
        'a': [],
        'hk': [],
        'us': []
    }
    unrecognized = []

    for code in stocks:
        found = False
        for ref_code, info in ref_data['stocks'].items():
            if code == ref_code or code == info['name'] or code in info.get('aliases', []):
                market = info.get('market', 'a')
                if ref_code not in classified[market]:
                    classified[market].append(ref_code)
                found = True
                break

        if not found:
            unrecognized.append(code)

    return classified, unrecognized


def _camel_to_snake(name):
    """Convert camelCase or PascalCase to snake_case."""
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def _normalize_quote(item):
    """Normalize a quote dict: rename camelCase keys to snake_case."""
    norm = {}
    for key, value in item.items():
        snake_key = _camel_to_snake(key)
        norm[snake_key] = value
    return norm


def _parse_opencli_output(stdout):
    """Parse opencli eastmoney quote output — handles both { data: [...] } and [...]."""
    if not stdout or not stdout.strip():
        return []
    raw = json.loads(stdout)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get('data', [])
    return []


def fetch_quotes(codes):
    """使用 opencli eastmoney quote 批量获取行情（支持所有市场）."""
    if not codes:
        return [], []

    cmd = ['opencli', 'eastmoney', 'quote', ','.join(codes), '-f', 'json']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return [], [f"Failed to fetch quotes: {result.stderr}"]

        items = _parse_opencli_output(result.stdout)
        quotes = [_normalize_quote(item) for item in items]
        return quotes, []
    except Exception as e:
        return [], [f"Error fetching quotes: {str(e)}"]


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_quotes.py <input> <output_file>")
        print("  input: 股票代码列表（JSON）或实体识别结果文件")
        print("  output_file: 输出文件路径")
        sys.exit(1)

    input_arg = sys.argv[1]
    output_file = sys.argv[2]

    # 加载参考数据
    script_dir = Path(__file__).parent
    ref_path = script_dir.parent.parent / 'extract-investment-entities' / 'references' / 'stock-codes.json'
    ref_data = load_stock_codes(ref_path)

    # 解析输入
    stocks = []

    if input_arg.endswith('.json'):
        with open(input_arg, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'data' in data and 'entities' in data['data']:
            stocks = [e['code'] for e in data['data']['entities'] if e['type'] == 'stock']
        elif 'stocks' in data:
            stocks = data['stocks']
    else:
        stocks = json.loads(input_arg)

    # 去重（保留首次出现顺序）
    seen = set()
    stocks_dedup = []
    for s in stocks:
        if s not in seen:
            seen.add(s)
            stocks_dedup.append(s)
    stocks = stocks_dedup

    # 分类股票，识别未知代码
    classified, unrecognized = classify_stocks(stocks, ref_data)

    # 收集所有需要查询的代码
    all_codes_to_fetch = classified['a'] + classified['hk'] + classified['us']

    # 未知代码 → 错误
    errors = []
    for code in unrecognized:
        errors.append(f"Unrecognized stock code: {code}")

    # 获取行情（单次调用 opencli eastmoney quote）
    all_quotes = []
    if all_codes_to_fetch:
        quotes, fetch_errors = fetch_quotes(all_codes_to_fetch)
        all_quotes = quotes
        errors.extend(fetch_errors)

    # 确定状态
    if not stocks:
        status = 'empty'
    elif errors and all_quotes:
        status = 'partial'
    elif errors and not all_quotes:
        status = 'failed'
    else:
        status = 'complete'

    # 生成 commands（记录实际调用）
    commands = []
    if all_codes_to_fetch:
        commands.append(
            f"opencli eastmoney quote {','.join(all_codes_to_fetch)} -f json"
        )

    # coverage: 按请求的代码数计算
    requested_count = len(stocks)
    succeeded_count = len(all_quotes)
    failed_count = max(0, requested_count - succeeded_count)

    # 生成输出
    output = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "status": status,
        "source": {
            "skill": "fetch-stock-quotes",
            "commands": commands
        },
        "coverage": {
            "requested": requested_count,
            "succeeded": succeeded_count,
            "failed": failed_count
        },
        "errors": errors,
        "data": {
            "quotes": all_quotes
        }
    }

    # 写入输出文件
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Fetched {len(all_quotes)} quotes to {output_file}")


if __name__ == '__main__':
    main()
