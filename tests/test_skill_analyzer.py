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


class TestRealKoreanMobile(unittest.TestCase):
    """2026-11-02 실제 eBay 한국어 모바일 화면을 옮겨 적은 데이터.

    가상 데이터로만 만든 첫 파서는 이 형식을 한 줄도 읽지 못했다. 다시 그렇게 되지 않도록 고정한다.
    """

    def setUp(self):
        path = ROOT / "tests" / "fixtures" / "real" / "pokemon_mobile_kr_2026-11-02.txt"
        self.listings, self.unparsed, self.fmt = al.parse(path.read_text(encoding="utf-8"), path.name)
        self.result = al.analyze(self.listings)
        # 제목 앞 N글자로 찾으면 이모지 때문에 위치가 밀려서, 제목에 들어 있는 단어로 찾는다
        self.find = lambda word: next(l for l in self.listings if word in l["title"])

    def test_counts_and_currency(self):
        self.assertEqual(self.result["counts"]["total"], 24)
        self.assertEqual((self.result["counts"]["sold"], self.result["counts"]["unsold"]), (16, 8))
        self.assertEqual(self.result["currency"], "KRW")
        self.assertEqual(self.unparsed, [])

    def test_discount_price_takes_current_price(self):
        # "₩2,521 · ₩2,655" → 앞의 할인된 가격
        self.assertEqual(self.find("Barraskewda")["price"], 2521.0)

    def test_shipping_variants(self):
        self.assertEqual(self.find("Gwynn")["shipping"], 30695.0)   # +배송비 ₩30,695
        self.assertEqual(self.find("SNORLAX")["shipping"], 0.0)       # 무료 국제 배송
        self.assertEqual(self.find("SNORLAX")["location"], "네덜란드")  # 출발지 네덜란드

    def test_auction_and_offer(self):
        gwynn = self.find("Gwynn")
        self.assertTrue(gwynn["auction"])
        self.assertEqual(gwynn["bids"], 0)
        houndoom = self.find("HOUNDOOM")
        self.assertTrue(houndoom["offer_accepted"])  # 베스트 오퍼 수락됨: 팔린 결과

    def test_missing_price_reported(self):
        self.assertEqual(self.result["missing_price"], 1)


if __name__ == "__main__":
    unittest.main()
