#!/usr/bin/env python3
"""采集市场新闻数据：东方财富快讯 + 知乎热门"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_opencli(args):
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
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_envelope(skill, commands, data, errors, requested, succeeded):
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
        "source": {"skill": skill, "commands": list(commands)},
        "coverage": {"requested": requested, "succeeded": succeeded, "failed": failed},
        "errors": list(errors),
        "data": data,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: collect.py <output_file>")
        sys.exit(1)

    output_file = sys.argv[1]
    limit = 20

    kuaixun, kuaixun_err = run_opencli(['eastmoney', 'kuaixun', '--limit', str(limit)])
    zhihu, zhihu_err = run_opencli(['zhihu', 'hot', '--limit', str(limit)])

    errors = []
    commands = []

    if kuaixun is None:
        errors.append(kuaixun_err)
    else:
        commands.append(f"opencli eastmoney kuaixun --limit {limit} -f json")

    if zhihu is None:
        errors.append(zhihu_err)
    else:
        commands.append(f"opencli zhihu hot --limit {limit} -f json")

    output = build_envelope(
        skill="collect-market-news",
        commands=commands,
        data={
            "kuaixun": kuaixun if kuaixun is not None else [],
            "zhihu_hot": zhihu if zhihu is not None else [],
        },
        errors=errors,
        requested=2,
        succeeded=len(commands),
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Market news collected to {output_file}")


if __name__ == '__main__':
    main()
