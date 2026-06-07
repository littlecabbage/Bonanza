#!/usr/bin/env python3
"""采集市场情绪数据：雪球热门股票 + 雪球热门帖子"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_opencli(args):
    """调用 opencli 命令，返回 (数据, 错误)."""
    cmd = ['opencli'] + args + ['-f', 'json']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            items = data if isinstance(data, list) else data.get('data', data)
            return items, None
        return None, f"{' '.join(cmd)}: {r.stderr.strip()}"
    except Exception as e:
        return None, f"{' '.join(cmd)}: {e}"


def now_iso():
    """当前时间 ISO 8601，含时区，无微秒."""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_envelope(skill, commands, data, errors, requested, succeeded):
    """构建标准信封结构."""
    failed = requested - succeeded
    if not errors:
        status = 'complete'
    elif succeeded > 0:
        status = 'partial'
    else:
        status = 'failed'

    return {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "status": status,
        "source": {
            "skill": skill,
            "commands": list(commands),
        },
        "coverage": {
            "requested": requested,
            "succeeded": succeeded,
            "failed": failed,
        },
        "errors": list(errors),
        "data": data,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: collect.py <output_file>")
        sys.exit(1)

    output_file = sys.argv[1]
    limit = 20

    # 1. 雪球热门股票
    stocks, stocks_err = run_opencli(['xueqiu', 'hot-stock', '--limit', str(limit)])
    if stocks is None:
        stocks = []

    # 2. 雪球热门帖子
    posts, posts_err = run_opencli(['xueqiu', 'hot', '--limit', str(limit)])
    if posts is None:
        posts = []

    # 汇总错误
    errors = []
    commands = []
    if stocks_err:
        errors.append(stocks_err)
    else:
        commands.append(f"opencli xueqiu hot-stock --limit {limit} -f json")
    if posts_err:
        errors.append(posts_err)
    else:
        commands.append(f"opencli xueqiu hot --limit {limit} -f json")

    succeeded = len(commands)
    requested = 2

    output = build_envelope(
        skill="collect-market-sentiment",
        commands=commands,
        data={
            "xueqiu_hot_stocks": stocks,
            "xueqiu_hot_posts": posts,
        },
        errors=errors,
        requested=requested,
        succeeded=succeeded,
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Market sentiment collected to {output_file}")


if __name__ == '__main__':
    main()
