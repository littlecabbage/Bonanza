#!/usr/bin/env python3
"""Tests for collect.py (collect-blogger-updates) — all subprocess.run calls are mocked."""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'skills',
    'collect-blogger-updates',
    'scripts',
    'collect.py',
)
spec = importlib.util.spec_from_file_location("collect_blogger_mod", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

SAMPLE_BLOGGER = {"username": "wallstreetbull", "name": "华尔街多头", "focus": "美股科技股"}
SAMPLE_TWEET = {
    "id_str": "123456789",
    "full_text": "AAPL looking strong today",
    "created_at": "2026-06-07T10:30:00+08:00",
    "url": "https://twitter.com/wallstreetbull/status/123456789",
    "favorite_count": 42,
    "retweet_count": 12,
}


def _mock_process(stdout_data, returncode=0):
    """Build a fake subprocess result."""
    p = MagicMock(spec=['returncode', 'stdout', 'stderr'])
    p.returncode = returncode
    p.stdout = json.dumps(stdout_data)
    p.stderr = ""
    return p


class TestCollectBloggerUpdates(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, input_arg=""):
        """Call collect.main() with given input and return parsed output."""
        out_path = os.path.join(self.test_dir, 'out.json')
        argv_save = sys.argv
        try:
            if input_arg:
                sys.argv = ['collect.py', input_arg, out_path]
            else:
                sys.argv = ['collect.py', out_path]
            collect.main()
        finally:
            sys.argv = argv_save
        with open(out_path) as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # 1. Correct command construction
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_TWEET]}))
    def test_correct_command_used(self, mock_run):
        """Should call opencli twitter tweets for each blogger."""
        bloggers_json = json.dumps([SAMPLE_BLOGGER])
        self._run(bloggers_json)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[1], 'twitter')
        self.assertEqual(args[2], 'tweets')
        self.assertIn(SAMPLE_BLOGGER['username'], args)

    # ------------------------------------------------------------------ #
    # 2. Source commands recorded
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_TWEET]}))
    def test_source_commands_recorded(self, mock_run):
        """source.commands should contain the twitter command string."""
        bloggers_json = json.dumps([SAMPLE_BLOGGER])
        output = self._run(bloggers_json)
        self.assertGreater(len(output['source']['commands']), 0)
        self.assertTrue(
            any('twitter tweets' in c for c in output['source']['commands'])
        )

    # ------------------------------------------------------------------ #
    # 3. Single blogger failure → partial
    # ------------------------------------------------------------------ #

    @patch('subprocess.run')
    def test_single_blogger_failure_is_partial(self, mock_run):
        """One blogger fails, another succeeds → status 'partial'."""
        mock_run.side_effect = [
            _mock_process({"data": [SAMPLE_TWEET]}),
            _mock_process([], returncode=1),
        ]
        bloggers = [
            {"username": "user1", "name": "User 1"},
            {"username": "user2", "name": "User 2"},
        ]
        output = self._run(json.dumps(bloggers))
        self.assertEqual(output['status'], 'partial')
        self.assertEqual(output['coverage']['succeeded'], 1)
        self.assertEqual(output['coverage']['failed'], 1)

    # ------------------------------------------------------------------ #
    # 4. All fail → failed
    # ------------------------------------------------------------------ #

    @patch('subprocess.run')
    def test_all_fail_is_failed(self, mock_run):
        """All bloggers fail → status 'failed'."""
        mock_run.return_value = _mock_process([], returncode=1)
        bloggers = [{"username": "user1", "name": "User 1"}]
        output = self._run(json.dumps(bloggers))
        self.assertEqual(output['status'], 'failed')

    # ------------------------------------------------------------------ #
    # 5. Output matches schema structure
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_TWEET]}))
    def test_output_matches_schema(self, mock_run):
        """Output should contain bloggers list with normalized tweets."""
        bloggers_json = json.dumps([SAMPLE_BLOGGER])
        output = self._run(bloggers_json)
        self.assertIn('bloggers', output['data'])
        self.assertEqual(len(output['data']['bloggers']), 1)
        blogger = output['data']['bloggers'][0]
        self.assertEqual(blogger['username'], SAMPLE_BLOGGER['username'])
        self.assertEqual(blogger['name'], SAMPLE_BLOGGER['name'])
        self.assertIn('tweets', blogger)
        tweet = blogger['tweets'][0]
        self.assertEqual(tweet['id'], SAMPLE_TWEET['id_str'])
        self.assertEqual(tweet['text'], SAMPLE_TWEET['full_text'])
        self.assertEqual(tweet['likes'], 42)
        self.assertEqual(tweet['retweets'], 12)

    # ------------------------------------------------------------------ #
    # 6. Timestamp with timezone
    # ------------------------------------------------------------------ #

    @patch('subprocess.run', return_value=_mock_process({"data": [SAMPLE_TWEET]}))
    def test_timestamp_has_timezone(self, mock_run):
        """generated_at must include timezone offset without microseconds."""
        bloggers_json = json.dumps([SAMPLE_BLOGGER])
        output = self._run(bloggers_json)
        ts = output['generated_at']
        self.assertIsNotNone(
            re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', ts)
        )
        self.assertNotIn('.', ts)


if __name__ == '__main__':
    unittest.main()