"""Google Trends 수집기 테스트 (네트워크 없이 샘플 XML 사용).

실행: python -m unittest discover tests
"""

import unittest
from pathlib import Path

from src.collectors.google_trends import collect, parse_traffic

SAMPLE = Path(__file__).parent / "fixtures" / "google_trends_sample.xml"


class TestParseTraffic(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_traffic("200+"), 200)

    def test_comma(self):
        self.assertEqual(parse_traffic("2,000+"), 2000)

    def test_k_and_m(self):
        self.assertEqual(parse_traffic("10K+"), 10_000)
        self.assertEqual(parse_traffic("1M+"), 1_000_000)

    def test_empty(self):
        self.assertEqual(parse_traffic(""), 0)


class TestCollect(unittest.TestCase):
    def test_from_sample_file(self):
        result = collect(file=str(SAMPLE))
        self.assertTrue(result["ok"])
        keywords = [it["keyword"] for it in result["items"]]
        # 대소문자만 다른 중복 키워드는 하나로 합쳐짐
        self.assertEqual(len(keywords), 3)
        # 검색량 내림차순 정렬
        self.assertEqual(keywords[0], "labubu blind box")
        self.assertEqual(len(result["items"][0]["news"]), 2)

    def test_failure_does_not_raise(self):
        result = collect(file="does_not_exist.xml")
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"], [])
        self.assertIn("FileNotFoundError", result["error"])


if __name__ == "__main__":
    unittest.main()
