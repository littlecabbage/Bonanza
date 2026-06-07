#!/usr/bin/env python3
"""采集资金异动数据：龙虎榜 + 资金流向 + 北向资金"""

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

    longhu, longhu_err = run_opencli(['eastmoney', 'longhu'])
    money_flow, money_flow_err = run_opencli(['eastmoney', 'money-flow'])
    northbound, northbound_err = run_opencli(['eastmoney', 'northbound'])

    errors = []
    commands = []

    if longhu is None:
        errors.append(longhu_err)
    else:
        commands.append("opencli eastmoney longhu -f json")

    if money_flow is None:
        errors.append(money_flow_err)
    else:
        commands.append("opencli eastmoney money-flow -f json")

    if northbound is None:
        errors.append(northbound_err)
    else:
        commands.append("opencli eastmoney northbound -f json")

    output = build_envelope(
        skill="collect-capital-movements",
        commands=commands,
        data={
            "longhu": longhu if longhu is not None else [],
            "money_flow": money_flow if money_flow is not None else [],
            "northbound": northbound if northbound is not None else [],
        },
        errors=errors,
        requested=3,
        succeeded=len(commands),
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Capital movements collected to {output_file}")


if __name__ == '__main__':
    main()