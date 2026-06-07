#!/usr/bin/env python3
"""Tests for extract_entities.py."""

import importlib.util
import json
import os
import re
import sys
import unittest

# Path setup
SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..',
    'skills',
    'extract-investment-entities',
    'scripts',
)
MODULE_PATH = os.path.join(SCRIPT_DIR, 'extract_entities.py')

spec = importlib.util.spec_from_file_location("extract_entities", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO_ROOT, 'schemas', 'investment-entities.schema.json')
with open(SCHEMA_PATH, encoding='utf-8') as f:
    SCHEMA = json.load(f)


class TestExtractEntities(unittest.TestCase):

    def setUp(self):
        self.ref_data = {
            "stocks": {
                "000725": {"name": "京东方A", "aliases": ["京东方", "BOE"], "market": "a"},
                "600519": {"name": "贵州茅台", "aliases": ["茅台", "maotai"], "market": "a"},
                "NVDA": {"name": "英伟达", "aliases": ["英伟达", "nvidia"], "market": "us"},
                "0700": {"name": "腾讯控股", "aliases": ["腾讯", "tencent"], "market": "hk"},
            },
            "industries": {
                "银行": {"code": "430037", "aliases": ["银行业", "银行股"]},
                "白酒": {"code": "430043", "aliases": ["白酒股", "酒类"]},
            },
            "concepts": {
                "国产替代": {"code": "BK1123", "aliases": ["国产化", "自主可控"]},
                "元宇宙": {"code": "BK1126", "aliases": ["metaverse"]},
            },
        }

    # --- 1. Chinese stock name maps to symbol ---

    def test_chinese_stock_name_maps_to_symbol(self):
        """京东方A should resolve to symbol 000725."""
        entities = mod.extract_entities("京东方A发布新品", self.ref_data)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]['symbol'], "000725")
        self.assertEqual(entities[0]['name'], "京东方A")

    # --- 2. US stock case insensitive ---

    def test_us_stock_case_insensitive(self):
        """NVDA and nvidia (alias) both match case-insensitively."""
        entities_upper = mod.extract_entities("关注NVDA股票", self.ref_data)
        self.assertEqual(len(entities_upper), 1)
        self.assertEqual(entities_upper[0]['symbol'], "NVDA")

        entities_lower = mod.extract_entities("关注nvidia股票", self.ref_data)
        self.assertEqual(len(entities_lower), 1)
        self.assertEqual(entities_lower[0]['symbol'], "NVDA")

    # --- 3. HK stock matching ---

    def test_hk_stock_matching(self):
        """HK stock 腾讯控股 should resolve to symbol 0700."""
        entities = mod.extract_entities("腾讯控股发布财报", self.ref_data)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]['symbol'], "0700")
        self.assertEqual(entities[0]['market'], "hk")

    # --- 4. Industry type is sector ---

    def test_industry_type_is_sector(self):
        """Industry entities should have type 'sector', not 'industry'."""
        entities = mod.extract_entities("看好银行业发展", self.ref_data)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]['type'], "sector")

    # --- 5. Concept type preserved ---

    def test_concept_type_preserved(self):
        """Concept entities should have type 'concept'."""
        entities = mod.extract_entities("关注国产替代", self.ref_data)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]['type'], "concept")

    # --- 6. Confidence is enum string ---

    def test_confidence_is_enum_string(self):
        """Confidence must be one of 'high', 'medium', 'low'."""
        entities = mod.extract_entities("茅台", self.ref_data)
        self.assertIn(entities[0]['confidence'], ("high", "medium", "low"))

    def test_confidence_low_for_one_mention(self):
        """Single mention yields confidence 'low'."""
        entities = mod.extract_entities("茅台", self.ref_data)
        self.assertEqual(entities[0]['confidence'], "low")

    def test_confidence_medium_for_two_mentions(self):
        """Two mentions yield confidence 'medium'."""
        entities = mod.extract_entities("茅台 and 茅台", self.ref_data)
        self.assertEqual(entities[0]['confidence'], "medium")

    def test_confidence_high_for_three_mentions(self):
        """Three or more mentions yield confidence 'high'."""
        entities = mod.extract_entities("茅台 茅台 茅台", self.ref_data)
        self.assertEqual(entities[0]['confidence'], "high")

    # --- 7. Mentions count real occurrences ---

    def test_mentions_count_real_occurrences(self):
        """Entity appearing 3 times should have mentions=3."""
        entities = mod.extract_entities("茅台 茅台 茅台", self.ref_data)
        self.assertEqual(entities[0]['mentions'], 3)

    # --- 8. Dedup preserves sources ---

    def test_dedup_preserves_sources(self):
        """Same entity from multiple sources should merge sources."""
        ents1 = mod.extract_entities("关注茅台", self.ref_data, "@source1")
        ents2 = mod.extract_entities("茅台上涨", self.ref_data, "@source2")
        merged = mod.merge_entities(ents1 + ents2)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['symbol'], "600519")
        self.assertIn("@source1", merged[0]['sources'])
        self.assertIn("@source2", merged[0]['sources'])

    # --- 9. Unrecognized text produces valid partial ---

    def test_unrecognized_text_produces_valid_partial(self):
        """No matches should return status 'partial' with valid empty output."""
        result = mod.build_result([], [], [])
        self.assertEqual(result['status'], "partial")
        self.assertEqual(result['data']['entities'], [])

    # --- 10. Timestamp has timezone, no microseconds ---

    def test_timestamp_has_timezone_no_microseconds(self):
        """generated_at must match ISO 8601 with timezone, no microseconds."""
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
        ts = mod.normalize_generated_at()
        self.assertRegex(ts, pattern)

    # --- 11. Output matches schema ---

    def test_output_matches_schema(self):
        """Output should contain all required fields from the schema."""
        entities = mod.extract_entities("茅台 茅台", self.ref_data, "@test")
        result = mod.build_result(entities, [], ["test-command"])

        required = SCHEMA.get('required', [])
        for field in required:
            self.assertIn(field, result, f"Missing required field: {field}")

        # Check entity required fields
        entity_schema = SCHEMA['properties']['data']['properties']['entities']['items']
        entity_required = entity_schema.get('required', [])
        for ent in result['data']['entities']:
            for field in entity_required:
                self.assertIn(field, ent, f"Missing required entity field: {field}")

    # --- 12. Corrupt input produces structured failed ---

    def test_corrupt_input_produces_structured_failed(self):
        """Invalid JSON should produce status 'failed' with error message."""
        result = mod.process_json_input('{corrupt json', self.ref_data)
        self.assertEqual(result['status'], "failed")
        self.assertTrue(len(result['errors']) > 0)
        self.assertNotIn("Traceback", str(result['errors']))


class TestExtractTextSources(unittest.TestCase):
    """Tests for extract_text_sources function."""

    def test_extracts_from_content_fields_only(self):
        """Only allowed fields should be extracted."""
        data = {
            "title": "股票分析",
            "content": "今天我们谈论茅台",
            "url": "http://example.com",
            "author": "测试",
            "error": "not found",
        }
        sources = mod.extract_text_sources(data)
        self.assertEqual(len(sources), 1)
        src, text = sources[0]
        self.assertEqual(src, "")
        self.assertIn("茅台", text)
        self.assertNotIn("http://example.com", text)

    def test_sources_from_posts(self):
        """Posts array should be processed per-source."""
        data = {
            "posts": [
                {"source": "@s1", "content": "茅台"},
                {"source": "@s2", "content": "英伟达"},
            ]
        }
        sources = mod.extract_text_sources(data)
        self.assertEqual(len(sources), 2)
        src_texts = dict(sources)
        self.assertIn("@s1", src_texts)
        self.assertIn("@s2", src_texts)
        self.assertIn("茅台", src_texts["@s1"])
        self.assertIn("英伟达", src_texts["@s2"])


if __name__ == '__main__':
    unittest.main()