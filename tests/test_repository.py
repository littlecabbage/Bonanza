#!/usr/bin/env python3
"""Repository validation baseline tests.

These tests establish a baseline for repository quality. Some tests
currently fail due to known issues in the legacy monolithic skill
that will be fixed during the modular refactor (Task 8).
"""

import unittest
import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, 'skills')


def parse_frontmatter(content):
    """Parse YAML frontmatter from a SKILL.md file.

    Minimal parser — no third-party YAML dependency.
    Returns (metadata_dict, body_text) or (None, content) if no frontmatter.
    """
    if not content.startswith('---'):
        return None, content
    end_idx = content.find('---', 3)
    if end_idx == -1:
        return None, content
    fm_text = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

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
    return metadata, body


class TestSkillFrontmatter(unittest.TestCase):
    """Verify all SKILL.md files have required frontmatter fields."""

    def _get_skill_dirs(self):
        if not os.path.isdir(SKILLS_DIR):
            return []
        return [
            os.path.join(SKILLS_DIR, d)
            for d in sorted(os.listdir(SKILLS_DIR))
            if os.path.isdir(os.path.join(SKILLS_DIR, d))
        ]

    def test_all_skills_have_valid_frontmatter(self):
        """Every SKILL.md must have frontmatter with name and description."""
        for skill_dir in self._get_skill_dirs():
            skill_md = os.path.join(skill_dir, 'SKILL.md')
            if not os.path.exists(skill_md):
                continue
            with open(skill_md, encoding='utf-8') as f:
                fm, body = parse_frontmatter(f.read())
            skill_name = os.path.basename(skill_dir)
            self.assertIsNotNone(
                fm,
                f"Skill '{skill_name}' has no YAML frontmatter"
            )
            self.assertIn(
                'name', fm,
                f"Skill '{skill_name}' missing 'name' in frontmatter"
            )
            self.assertIn(
                'description', fm,
                f"Skill '{skill_name}' missing 'description' in frontmatter"
            )

    def test_skill_name_matches_directory(self):
        """Frontmatter 'name' should match the skill directory name."""
        for skill_dir in self._get_skill_dirs():
            skill_md = os.path.join(skill_dir, 'SKILL.md')
            if not os.path.exists(skill_md):
                continue
            with open(skill_md, encoding='utf-8') as f:
                fm, _ = parse_frontmatter(f.read())
            if fm is None or 'name' not in fm:
                continue
            dir_name = os.path.basename(skill_dir)
            self.assertEqual(
                fm['name'], dir_name,
                f"Directory '{dir_name}' has frontmatter name '{fm['name']}'"
            )


class TestJsonFiles(unittest.TestCase):
    """Verify all JSON reference files are syntactically valid."""

    def _get_json_files(self):
        json_files = []
        if not os.path.isdir(SKILLS_DIR):
            return json_files
        for skill_name in sorted(os.listdir(SKILLS_DIR)):
            refs_dir = os.path.join(SKILLS_DIR, skill_name, 'references')
            if not os.path.isdir(refs_dir):
                continue
            for fn in sorted(os.listdir(refs_dir)):
                if fn.endswith('.json'):
                    json_files.append(os.path.join(refs_dir, fn))
        return json_files

    def test_all_json_files_are_valid(self):
        """Every JSON file must parse without errors."""
        for fpath in self._get_json_files():
            with open(fpath, encoding='utf-8') as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {fpath}: {e}")


class TestHtmlTemplate(unittest.TestCase):
    """Check HTML template for structural issues.

    Known baseline issues (to be fixed in Task 8):
    - Section "一、投资建议（核心）" appears twice (lines 333 and 696)
    - SKILL.md uses .advice-buy-strong, template uses .advice-strong-buy
    """

    TEMPLATE_PATH = os.path.join(
        SKILLS_DIR,
        'opencli-investment-report',
        'references',
        'report-template.html'
    )
    SKILL_MD_PATH = os.path.join(
        SKILLS_DIR,
        'opencli-investment-report',
        'SKILL.md'
    )

    def _read_template(self):
        with open(self.TEMPLATE_PATH, encoding='utf-8') as f:
            return f.read()

    def _read_skill_md(self):
        with open(self.SKILL_MD_PATH, encoding='utf-8') as f:
            return f.read()

    def test_no_duplicate_h2_sections(self):
        """Template must not have duplicate <h2> sections.

        KNOWN FAILURE: "一、投资建议（核心）" appears twice.
        Will be fixed in Task 8 when template is cleaned up.
        """
        content = self._read_template()
        h2_pattern = re.compile(r'<h2>\s*([^<]+)\s*</h2>')
        headings = h2_pattern.findall(content)
        seen = {}
        duplicates = []
        for h in headings:
            seen[h] = seen.get(h, 0) + 1
            if seen[h] > 1:
                duplicates.append(h)
        self.assertEqual(
            len(duplicates), 0,
            f"Duplicate <h2> sections found: {duplicates}. "
            f"Known issue to be fixed in Task 8."
        )

    def test_css_class_consistency(self):
        """CSS class names in SKILL.md must match those in HTML template.

        KNOWN FAILURE: SKILL.md uses .advice-buy-strong,
        but HTML template uses .advice-strong-buy.
        Will be fixed in Task 8.
        """
        skill_content = self._read_skill_md()
        html_content = self._read_template()

        skill_classes = set(re.findall(r'\.advice-[\w-]+', skill_content))
        html_classes = set(re.findall(r'\.advice-[\w-]+', html_content))

        # Remove level-variant classes (those are consistent)
        skill_advice = {c for c in skill_classes if 'level' not in c}
        html_advice = {c for c in html_classes if 'level' not in c}

        inconsistent = skill_advice.symmetric_difference(html_advice)
        # .advice-grid and .advice-grid-item only exist in HTML template (expected)
        inconsistent.discard('.advice-grid')
        inconsistent.discard('.advice-grid-item')

        self.assertEqual(
            len(inconsistent), 0,
            f"CSS class mismatch between SKILL.md and template: {inconsistent}. "
            f"Known: SKILL.md has .advice-buy-strong, HTML has .advice-strong-buy."
        )

    def test_placeholder_count_documented(self):
        """Template placeholders should be tracked for render validation.

        In the template source, placeholders are expected.
        When Task 8 implements deterministic rendering, a separate test
        will verify that rendered HTML has zero residual placeholders.
        """
        content = self._read_template()
        placeholders = re.findall(r'\{\{[^}]+\}\}', content)
        # Template MUST have placeholders for data injection — this is normal.
        self.assertGreater(
            len(placeholders), 0,
            "Template must have placeholders for data injection"
        )


class TestWorkflowGuideSkill(unittest.TestCase):
    """Verify guide-investment-workflow skill structure."""

    GUIDE_SKILL_DIR = os.path.join(SKILLS_DIR, 'guide-investment-workflow')

    def test_guide_skill_has_required_files(self):
        """Guide skill must have SKILL.md, agents/openai.yaml, and scripts."""
        required_files = [
            'SKILL.md',
            'agents/openai.yaml',
            'scripts/inspect_run.py',
            'references/workflow.md'
        ]
        for relpath in required_files:
            fpath = os.path.join(self.GUIDE_SKILL_DIR, relpath)
            self.assertTrue(
                os.path.exists(fpath),
                f"Guide skill missing required file: {relpath}"
            )

    def test_guide_skill_frontmatter_complete(self):
        """Guide skill frontmatter must include name and description."""
        skill_md = os.path.join(self.GUIDE_SKILL_DIR, 'SKILL.md')
        with open(skill_md, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, body = parse_frontmatter(content)

        self.assertIsNotNone(metadata, "Guide skill missing frontmatter")
        self.assertIn('name', metadata, "Guide skill missing 'name'")
        self.assertIn('description', metadata, "Guide skill missing 'description'")
        self.assertEqual(
            metadata['name'],
            'guide-investment-workflow',
            "Guide skill name mismatch"
        )

    def test_inspect_run_script_executable(self):
        """inspect_run.py must be executable and contain main function."""
        script_path = os.path.join(
            self.GUIDE_SKILL_DIR,
            'scripts',
            'inspect_run.py'
        )

        # Check executable permission
        self.assertTrue(
            os.access(script_path, os.X_OK),
            "inspect_run.py is not executable"
        )

        # Check script content
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('def inspect_run', content, "Missing inspect_run function")
        self.assertIn('def main', content, "Missing main function")
        self.assertIn('workflow-state.json', content, "Missing workflow state handling")

    def test_workflow_reference_completeness(self):
        """workflow.md must document skill dependencies and data freshness."""
        ref_path = os.path.join(
            self.GUIDE_SKILL_DIR,
            'references',
            'workflow.md'
        )

        with open(ref_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check key sections exist
        required_sections = [
            '技能依赖关系',
            '数据新鲜度策略',
            '单点任务示例',
            '错误处理'
        ]
        for section in required_sections:
            self.assertIn(
                section,
                content,
                f"workflow.md missing section: {section}"
            )

        # Check skill table exists
        self.assertIn('collect-market-overview', content)
        self.assertIn('analyze-investment-signals', content)
        self.assertIn('render-investment-report', content)


class TestDataContracts(unittest.TestCase):
    """Verify schema files and fixture compliance with data contracts."""

    SCHEMAS_DIR = os.path.join(REPO_ROOT, 'schemas')
    FIXTURES_DIR = os.path.join(REPO_ROOT, 'tests', 'fixtures')

    # Common envelope fields required on every JSON output
    ENVELOPE_FIELDS = [
        'schema_version', 'generated_at', 'status',
        'source', 'coverage', 'errors', 'data'
    ]

    # workflow-state has a different schema (orchestration, not business data)
    NON_BUSINESS_FIXTURES = {'valid-workflow-state.json', 'invalid-workflow-state.json'}

    def _load_json(self, relpath):
        fpath = os.path.join(self.FIXTURES_DIR, relpath)
        with open(fpath, encoding='utf-8') as f:
            return json.load(f)

    def test_all_schema_files_exist(self):
        """All expected schema files must be present."""
        expected_schemas = [
            'workflow-state.schema.json',
            'blogger-updates.schema.json',
            'market-overview.schema.json',
            'market-sentiment.schema.json',
            'capital-movements.schema.json',
            'market-news.schema.json',
            'investment-entities.schema.json',
            'stock-quotes.schema.json',
            'investment-signals.schema.json',
            'investment-scenarios.schema.json',
        ]
        for schema_name in expected_schemas:
            fpath = os.path.join(self.SCHEMAS_DIR, schema_name)
            self.assertTrue(
                os.path.exists(fpath),
                f"Missing schema: {schema_name}"
            )
            # Also validate they are valid JSON
            with open(fpath, encoding='utf-8') as f:
                json.load(f)

    def test_all_schema_files_have_correct_version(self):
        """Every schema must pin schema_version to '1.0'."""
        for fn in sorted(os.listdir(self.SCHEMAS_DIR)):
            if not fn.endswith('.schema.json'):
                continue
            fpath = os.path.join(self.SCHEMAS_DIR, fn)
            with open(fpath, encoding='utf-8') as f:
                schema = json.load(f)
            # Check the const constraint exists for schema_version
            props = schema.get('properties', {})
            sv = props.get('schema_version', {})
            self.assertEqual(
                sv.get('const'), '1.0',
                f"Schema '{fn}' must pin schema_version to '1.0'"
            )

    def test_valid_fixtures_have_envelope_fields(self):
        """All valid-* fixtures must contain the standard envelope fields."""
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.startswith('valid-') or not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            for field in self.ENVELOPE_FIELDS:
                self.assertIn(
                    field, data,
                    f"Fixture '{fn}' missing envelope field: {field}"
                )

    def test_valid_fixtures_have_schema_version_1(self):
        """All valid fixtures must declare schema_version '1.0'."""
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.startswith('valid-') or not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            self.assertEqual(
                data.get('schema_version'), '1.0',
                f"Fixture '{fn}' must have schema_version='1.0'"
            )

    def test_valid_fixtures_have_timezone_in_generated_at(self):
        """generated_at must include timezone offset."""
        tz_pattern = re.compile(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'
        )
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.startswith('valid-') or not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            generated_at = data.get('generated_at', '')
            self.assertTrue(
                tz_pattern.match(generated_at),
                f"Fixture '{fn}' generated_at='{generated_at}' "
                f"must match ISO 8601 with timezone"
            )

    def test_invalid_fixtures_fail_specific_validation(self):
        """Each invalid fixture should fail its specific validation test.

        - invalid-market-overview.json: missing envelope fields
        - invalid-blogger-updates.json: missing envelope fields
        - invalid-stock-quotes-no-timezone.json: invalid timezone format
        """
        fixtures_dir = os.path.join(REPO_ROOT, 'tests', 'fixtures')

        # Test envelope-invalid fixtures
        envelope_invalid = {
            'invalid-market-overview.json',
            'invalid-blogger-updates.json'
        }
        for fn in envelope_invalid:
            fpath = os.path.join(fixtures_dir, fn)
            if not os.path.exists(fpath):
                continue
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            missing = [
                field for field in self.ENVELOPE_FIELDS if field not in data
            ]
            self.assertGreater(
                len(missing), 0,
                f"Fixture '{fn}' should be missing envelope fields"
            )

        # Test timezone-invalid fixture
        tz_invalid = 'invalid-stock-quotes-no-timezone.json'
        tz_path = os.path.join(fixtures_dir, tz_invalid)
        if os.path.exists(tz_path):
            with open(tz_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tz_pattern = re.compile(
                r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'
            )
            generated_at = data.get('generated_at', '')
            self.assertFalse(
                tz_pattern.match(generated_at),
                f"Fixture '{tz_invalid}' should have invalid timezone format"
            )

    def test_valid_status_values(self):
        """All fixtures with status field must use allowed values."""
        allowed = {'complete', 'partial', 'failed'}
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            if 'status' in data:
                self.assertIn(
                    data['status'], allowed,
                    f"Fixture '{fn}' has invalid status: {data['status']}"
                )

    def test_partial_status_has_errors_or_coverage(self):
        """Partial status must explain what's missing via errors or coverage."""
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            if data.get('status') != 'partial':
                continue
            has_errors = bool(data.get('errors'))
            coverage = data.get('coverage', {})
            has_coverage_gap = (
                coverage.get('failed', 0) > 0 or
                coverage.get('succeeded', 0) < coverage.get('requested', 0)
            )
            self.assertTrue(
                has_errors or has_coverage_gap,
                f"Fixture '{fn}' has status='partial' but no errors or "
                f"coverage gap to explain what's missing"
            )

    def test_coverage_fields_are_non_negative(self):
        """Coverage requested/succeeded/failed must be non-negative integers."""
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            coverage = data.get('coverage')
            if not coverage:
                continue
            for key in ['requested', 'succeeded', 'failed']:
                val = coverage.get(key, 0)
                self.assertIsInstance(
                    val, int,
                    f"Fixture '{fn}' coverage.{key} must be int, got {type(val)}"
                )
                self.assertGreaterEqual(
                    val, 0,
                    f"Fixture '{fn}' coverage.{key} must be >= 0"
                )

    def test_source_commands_is_list(self):
        """source.commands must be a list of strings."""
        for fn in sorted(os.listdir(self.FIXTURES_DIR)):
            if not fn.startswith('valid-') or not fn.endswith('.json'):
                continue
            if fn in self.NON_BUSINESS_FIXTURES:
                continue
            data = self._load_json(fn)
            source = data.get('source', {})
            commands = source.get('commands')
            self.assertIsInstance(
                commands, list,
                f"Fixture '{fn}' source.commands must be a list"
            )
            for cmd in commands:
                self.assertIsInstance(
                    cmd, str,
                    f"Fixture '{fn}' source.commands contains non-string: {cmd}"
                )


if __name__ == '__main__':
    unittest.main()