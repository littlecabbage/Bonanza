#!/usr/bin/env python3
"""Repository validation script.

Checks skill structure, JSON validity, and HTML template issues.
Reports each check as PASS, FAIL, WARN, or INFO.
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, 'skills')


def parse_frontmatter(content):
    """Minimal YAML frontmatter parser — no third-party dependency."""
    if not content.startswith('---'):
        return None
    end_idx = content.find('---', 3)
    if end_idx == -1:
        return None
    fm_text = content[3:end_idx].strip()
    metadata = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        colon_idx = line.find(':')
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        value = line[colon_idx + 1:].strip()
        metadata[key] = value.strip('"').strip("'")
    return metadata


def check_skill_frontmatter():
    """Check all SKILL.md files have required frontmatter."""
    results = []
    if not os.path.isdir(SKILLS_DIR):
        results.append(('FAIL', 'skills/ directory not found'))
        return results

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, skill_name)
        if not os.path.isdir(skill_dir):
            continue
        skill_md = os.path.join(skill_dir, 'SKILL.md')
        if not os.path.exists(skill_md):
            results.append(('SKIP', f'{skill_name}: no SKILL.md'))
            continue
        with open(skill_md, encoding='utf-8') as f:
            fm = parse_frontmatter(f.read())
        if fm is None:
            results.append(('FAIL', f'{skill_name}: missing frontmatter'))
            continue
        issues = []
        if 'name' not in fm:
            issues.append('missing "name"')
        elif fm['name'] != skill_name:
            results.append(('WARN', f'{skill_name}: name="{fm["name"]}" ≠ dir name'))
        if 'description' not in fm:
            issues.append('missing "description"')
        if issues:
            results.append(('FAIL', f'{skill_name}: {", ".join(issues)}'))
        else:
            results.append(('PASS', f'{skill_name}: frontmatter valid'))
    return results


def check_json_files():
    """Check all JSON reference files are syntactically valid."""
    results = []
    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        refs_dir = os.path.join(SKILLS_DIR, skill_name, 'references')
        if not os.path.isdir(refs_dir):
            continue
        for fn in sorted(os.listdir(refs_dir)):
            if not fn.endswith('.json'):
                continue
            fpath = os.path.join(refs_dir, fn)
            try:
                with open(fpath, encoding='utf-8') as f:
                    json.load(f)
                results.append(('PASS', f'{fpath}: valid JSON'))
            except json.JSONDecodeError as e:
                results.append(('FAIL', f'{fpath}: invalid JSON — {e}'))
    if not any(s == 'PASS' for s, _ in results):
        results.append(('INFO', 'No JSON files found'))
    return results


def check_html_template():
    """Check HTML template for structural issues.

    Expected at skills/render-investment-report/assets/report-template.html.
    Until that skill is created, reports SKIP.
    """
    results = []
    template_path = os.path.join(
        SKILLS_DIR, 'render-investment-report', 'assets', 'report-template.html'
    )
    skill_md_path = os.path.join(
        SKILLS_DIR, 'render-investment-report', 'SKILL.md'
    )

    if not os.path.exists(template_path):
        results.append(('SKIP', 'HTML template not yet created (pending render-investment-report skill)'))
        return results

    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    # Duplicate <h2> sections
    h2_pattern = re.compile(r'<h2>\s*([^<]+)\s*</h2>')
    headings = h2_pattern.findall(html)
    seen = {}
    for h in headings:
        seen[h] = seen.get(h, 0) + 1
    duplicates = {h: c for h, c in seen.items() if c > 1}
    if duplicates:
        for h, count in duplicates.items():
            results.append(('FAIL', f'Duplicate section: "{h}" appears {count} times'))
    else:
        results.append(('PASS', 'No duplicate <h2> sections'))

    # CSS class consistency (only if SKILL.md exists)
    if os.path.exists(skill_md_path):
        with open(skill_md_path, encoding='utf-8') as f:
            skill_md = f.read()
        skill_classes = set(re.findall(r'\.advice-[\w-]+', skill_md))
        html_classes = set(re.findall(r'\.advice-[\w-]+', html))
        skill_advice = {c for c in skill_classes if 'level' not in c}
        html_advice = {c for c in html_classes if 'level' not in c}
        inconsistent = skill_advice.symmetric_difference(html_advice)
        inconsistent.discard('.advice-grid')
        inconsistent.discard('.advice-grid-item')
        if inconsistent:
            for c in sorted(inconsistent):
                in_skill = c in skill_classes
                in_html = c in html_classes
                results.append(('FAIL', f'CSS "{c}": SKILL.md={in_skill}, HTML={in_html}'))
        else:
            results.append(('PASS', 'CSS class names consistent'))

    # Placeholder count
    placeholders = re.findall(r'\{\{[^}]+\}\}', html)
    results.append(('INFO', f'{len(placeholders)} template placeholders (expected in source)'))

    return results


def main():
    print("Bonanza Repository Validation")
    print("=" * 50)

    all_results = []

    print("\n[Skill Frontmatter]")
    results = check_skill_frontmatter()
    for status, msg in results:
        print(f"  {status:5s}  {msg}")
    all_results.extend(results)

    print("\n[JSON Files]")
    results = check_json_files()
    for status, msg in results:
        print(f"  {status:5s}  {msg}")
    all_results.extend(results)

    print("\n[HTML Template]")
    results = check_html_template()
    for status, msg in results:
        print(f"  {status:5s}  {msg}")
    all_results.extend(results)

    # Summary
    fail_count = sum(1 for s, _ in all_results if s == 'FAIL')
    pass_count = sum(1 for s, _ in all_results if s == 'PASS')
    warn_count = sum(1 for s, _ in all_results if s == 'WARN')

    print(f"\n{'=' * 50}")
    print(f"PASS: {pass_count}  FAIL: {fail_count}  WARN: {warn_count}")

    if fail_count > 0:
        print("\nSome checks failed. Known baseline issues exist in the legacy")
        print("skill and will be fixed during the modular refactor (Task 8).")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())