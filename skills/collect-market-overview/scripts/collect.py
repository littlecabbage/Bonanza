#!/usr/bin/env python3
"""Collect market overview data via opencli eastmoney commands."""

import json
import re
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
            return data if isinstance(data, list) else data.get('data', data), None
        return None, f"{' '.join(cmd)}: {r.stderr.strip()}"
    except Exception as e:
        return None, f"{' '.join(cmd)}: {e}"


def now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_envelope(skill, commands, data, errors, requested, succeeded):
    status = 'complete' if not errors else ('partial' if succeeded else 'failed')
    return {
        "schema_version": "1.0", "generated_at": now_iso(), "status": status,
        "source": {"skill": skill, "commands": commands},
        "coverage": {"requested": requested, "succeeded": succeeded, "failed": requested - succeeded},
        "errors": errors, "data": data
    }


def _camel_to_snake(name):
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def _normalize(item):
    norm = {}
    for key, value in item.items():
        snake_key = _camel_to_snake(key)
        norm[snake_key] = value
    return norm


def main():
    if len(sys.argv) < 2:
        print("Usage: collect.py <output_file>")
        sys.exit(1)

    output_file = sys.argv[-1]

    commands = []
    data = {}
    errors = []
    requested = 3
    succeeded = 0

    # 1. Indices
    cmd_indices = ['eastmoney', 'index-board']
    cmd_str = f"opencli {' '.join(cmd_indices)} -f json"
    commands.append(cmd_str)
    indices_data, err = run_opencli(cmd_indices)
    if err:
        errors.append(err)
        data['indices'] = []
    else:
        succeeded += 1
        data['indices'] = [_normalize(item) for item in (indices_data if isinstance(indices_data, list) else [])]

    # 2. Hot stocks
    cmd_hot = ['eastmoney', 'hot-rank', '--limit', '20']
    cmd_str = f"opencli {' '.join(cmd_hot)} -f json"
    commands.append(cmd_str)
    hot_data, err = run_opencli(cmd_hot)
    if err:
        errors.append(err)
        data['hot_stocks'] = []
    else:
        succeeded += 1
        data['hot_stocks'] = [_normalize(item) for item in (hot_data if isinstance(hot_data, list) else [])]

    # 3. Sectors
    cmd_sectors = ['eastmoney', 'sectors', '--limit', '20']
    cmd_str = f"opencli {' '.join(cmd_sectors)} -f json"
    commands.append(cmd_str)
    sectors_data, err = run_opencli(cmd_sectors)
    if err:
        errors.append(err)
        data['sectors'] = []
    else:
        succeeded += 1
        data['sectors'] = [_normalize(item) for item in (sectors_data if isinstance(sectors_data, list) else [])]

    output = build_envelope(
        skill="collect-market-overview",
        commands=commands,
        data=data,
        errors=errors,
        requested=requested,
        succeeded=succeeded,
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Collected market overview: {succeeded}/{requested} sources → {output_file}")


if __name__ == '__main__':
    main()