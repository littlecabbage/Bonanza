#!/usr/bin/env python3
"""Collect blogger updates from Twitter via opencli."""

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


def normalize_tweet(tweet):
    """Normalize a raw tweet dict to schema fields."""
    return {
        "id": str(tweet.get('id_str', tweet.get('id', ''))),
        "text": tweet.get('full_text', tweet.get('text', '')),
        "created_at": tweet.get('created_at', ''),
        "url": tweet.get('url', ''),
        "likes": int(tweet.get('favorite_count', tweet.get('likes', 0))),
        "retweets": int(tweet.get('retweet_count', tweet.get('retweets', 0))),
    }


def load_bloggers(ref_path):
    """Load blogger list from references/bloggers.json."""
    with open(ref_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('bloggers', data) if isinstance(data, dict) else data


def main():
    if len(sys.argv) < 2:
        print("Usage: collect.py [input_json] <output_file>")
        sys.exit(1)

    output_file = sys.argv[-1]

    # Determine blogger list source
    if len(sys.argv) == 3:
        input_arg = sys.argv[1]
        if input_arg.endswith('.json'):
            with open(input_arg, 'r', encoding='utf-8') as f:
                bloggers = json.load(f)
        else:
            bloggers = json.loads(input_arg)
    else:
        # Default: read from references/bloggers.json
        script_dir = Path(__file__).parent
        ref_path = script_dir.parent / 'references' / 'bloggers.json'
        bloggers = load_bloggers(ref_path)

    # Ensure bloggers is a list
    if isinstance(bloggers, dict):
        bloggers = bloggers.get('bloggers', [])
    if not isinstance(bloggers, list):
        bloggers = [bloggers]

    commands = []
    errors = []
    bloggers_output = []

    for blogger in bloggers:
        username = blogger.get('username', '')
        if not username:
            continue

        cmd_args = ['twitter', 'tweets', username, '--limit', '5']
        cmd_str = f"opencli {' '.join(cmd_args)} -f json"
        commands.append(cmd_str)

        data, err = run_opencli(cmd_args)
        if err:
            errors.append(err)
            bloggers_output.append({
                "username": username,
                "name": blogger.get('name', username),
                "tweets": []
            })
        else:
            tweets_list = data if isinstance(data, list) else []
            bloggers_output.append({
                "username": username,
                "name": blogger.get('name', username),
                "tweets": [normalize_tweet(t) for t in tweets_list]
            })

    requested = len(bloggers)
    succeeded = sum(1 for b in bloggers_output if b['tweets'])

    output = build_envelope(
        skill="collect-blogger-updates",
        commands=commands,
        data={"bloggers": bloggers_output},
        errors=errors,
        requested=requested,
        succeeded=succeeded,
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Collected updates for {succeeded}/{requested} bloggers → {output_file}")


if __name__ == '__main__':
    main()