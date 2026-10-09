"""Reddit 수집기 테스트 (네트워크 없이 샘플 데이터 사용)."""

import unittest
import urllib.error
from pathlib import Path

from src.collectors.reddit import error_label, hot_score, is_excluded, parse_rss

SAMPLE = Path(__file__).parent / "fixtures" / "reddit_sample.xml"
NOW = 1791536400  # 2026-10-09 09:00 UTC
EXCLUDE = [
    "\\b(daily|weekly|monthly)\\b.*\\b(thread|discussion|help|questions?)\\b",
    "\\bthread\\b",
    "\\brules?\\b",
    "\\bmods?\\b",
]


class TestHelpers(unittest.TestCase):
    def test_hot_score(self):
        self.assertEqual(hot_score(1, 10), 1.0)
        self.assertEqual(hot_score(10, 10), 0.1)
        self.assertEqual(hot_score(1, 0), 0.0)

    def test_error_label_shows_status_code(self):
        e = urllib.error.HTTPError("u", 429, "Too Many Requests", None, None)
        self.assertEqual(error_label(e), "HTTP 429")

    def test_is_excluded(self):
        self.assertTrue(is_excluded("Weekly Discussion THREAD", EXCLUDE))
        self.assertTrue(is_excluded("Message from the mods", EXCLUDE))
        self.assertTrue(is_excluded("NEW OR NEED HELP? Ask here! - ScA Daily Help Thread", EXCLUDE))
        # 단어 일부이거나 상품 글이면 제외하지 않음
        self.assertFalse(is_excluded("Modern lamp that went viral", EXCLUDE))
        self.assertFalse(is_excluded("My daily sunscreen finally restocked", EXCLUDE))
        self.assertFalse(is_excluded("This ruler is BIFL", EXCLUDE))


class TestParseRss(unittest.TestCase):
    def setUp(self):
        self.posts = parse_rss(SAMPLE.read_bytes(), EXCLUDE, keep_top=10, now=NOW)
        self.by_title = {p["title"]: p for p in self.posts}

    def test_excluded_titles_removed(self):
        self.assertNotIn("Weekly Discussion Thread", self.by_title)
        self.assertEqual(len(self.posts), 4)

    def test_rank_is_per_subreddit(self):
        # 그룹 피드에 섞여 있어도 순위는 서브레딧 안에서 따로 매김
        self.assertEqual(self.by_title["Finally finished the new Botanical set"]["rank"], 1)
        self.assertEqual(self.by_title["New album pre-orders sold out in an hour"]["rank"], 1)
        self.assertEqual(self.by_title["Lightstick restock?"]["rank"], 2)

    def test_subreddit_from_url_when_no_category(self):
        p = self.by_title["Post without category tag"]
        self.assertEqual(p["subreddit"], "lego")
        self.assertEqual(p["rank"], 2)

    def test_age(self):
        self.assertEqual(self.by_title["Finally finished the new Botanical set"]["age_hours"], 4.0)

    def test_keep_top(self):
        posts = parse_rss(SAMPLE.read_bytes(), EXCLUDE, keep_top=1, now=NOW)
        self.assertEqual(len(posts), 2)  # 서브레딧당 1개씩


if __name__ == "__main__":
    unittest.main()
