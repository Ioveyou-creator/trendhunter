"""ebay-seo-lens 스킬의 답안지 분석 스크립트 테스트.

스킬의 평가용 가상 데이터(skills/ebay-seo-lens/evals/*/files)를 그대로 사용한다.
"""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "ebay-seo-lens"
spec = importlib.util.spec_from_file_location("analyze_listings", SKILL / "scripts" / "analyze_listings.py")
al = importlib.util.module_from_spec(spec)
spec.loader.exec_module(al)


def load(case: str, name: str):
    path = SKILL / "evals" / case / "files" / name
    listings, unparsed, fmt = al.parse(path.read_text(encoding="utf-8"), name)
    return listings, unparsed, fmt, al.analyze(listings)


class TestParseEbayText(unittest.TestCase):
    def setUp(self):
        self.listings, self.unparsed, self.fmt, self.result = load("kpop-photocard-keyword", "nova_orbit.txt")

    def test_counts(self):
        self.assertEqual(self.fmt, "ebay_text")
        self.assertEqual(self.result["counts"], {"total": 20, "sold": 10, "unsold": 10, "sell_through": 0.5})

    def test_fields(self):
        first = self.listings[0]
        self.assertEqual(first["title"], "NOVA 2nd Mini Album Orbit Korean Ver Sealed with Photocard POB")
        self.assertEqual(first["price"], 24.99)
        self.assertEqual(first["shipping"], 0.0)
        self.assertEqual(first["location"], "South Korea")

    def test_page_header_is_not_unparsed(self):
        # 검색창·필터 등 첫 리스팅 이전 줄은 '인식 못 한 줄'로 세지 않는다
        self.assertEqual(self.unparsed, [])

    def test_photocard_keyword_gap(self):
        pc = next(k for k in self.result["keywords_top"] if k["feature"] == "photocard")
        self.assertEqual(pc["with"]["sell_through"], 0.8)
        self.assertEqual(pc["without"]["sell_through"], 0.2)

    def test_free_shipping_has_no_effect(self):
        free = next(f for f in self.result["features"] if f["feature"] == "무료 배송")
        self.assertEqual(free["gap"], 0.0)


class TestParseCsv(unittest.TestCase):
    def test_shipping_confound(self):
        listings, unparsed, fmt, result = load("tcg-shipping-confound", "starlight_box.csv")
        self.assertEqual(fmt, "csv")
        self.assertEqual(result["counts"]["sold"], 9)
        self.assertEqual(result["price"]["median_total_sold"], 97.0)
        self.assertEqual(result["price"]["median_total_unsold"], 107.0)
        free = next(f for f in result["features"] if f["feature"] == "무료 배송")
        self.assertEqual(free["gap"], 1.0)

    def test_csv_missing_columns_reported(self):
        listings, unparsed = al.parse_csv("name,cost\nfoo,1\n")
        self.assertEqual(listings, [])
        self.assertTrue(any("title, status" in u for u in unparsed))


class TestSmallSample(unittest.TestCase):
    def test_small_sample_flag(self):
        _, _, _, result = load("small-sample-holds-back", "lumi_lightstick.txt")
        self.assertTrue(result["small_sample"])
        self.assertEqual((result["counts"]["sold"], result["counts"]["unsold"]), (2, 3))


class TestNoListings(unittest.TestCase):
    def test_text_without_status_lines(self):
        listings, unparsed, fmt = al.parse("just some random text\nwithout listings\n")
        self.assertEqual(listings, [])


if __name__ == "__main__":
    unittest.main()
