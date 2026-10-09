"""점수화 테스트. 실제 config/scoring.yaml 규칙 + 2026-10-09 실제 수집된 제목 일부를 사용."""

import unittest
from urllib.parse import unquote_plus

from src.config import load_yaml
from src.scoring import Rules, build, make_links, make_query, norm_key

SCORING = load_yaml("scoring.yaml")
RULES = Rules(SCORING)
SOURCES = {"reddit": {"groups": {"collectibles": ["PokemonTCG"], "kculture": ["AsianBeauty", "kpop"]}}}


def reddit_post(title, sub="PokemonTCG", rank=1, hot=1.0):
    return {"title": title, "subreddit": sub, "rank": rank, "hot_score": hot,
            "url": f"https://www.reddit.com/r/{sub}/comments/x/"}


def trend(keyword, traffic, news=()):
    return {"keyword": keyword, "traffic": traffic, "traffic_label": f"{traffic}+",
            "news": [{"title": n, "url": "https://example.com"} for n in news]}


EVENT = {
    "name": "Pokemon 30th Celebration UPC", "category": "tcg", "date": "2026-11-06",
    "days_left": 28, "prep_by": "2026-10-30", "status": "upcoming",
    "keywords": ["pokemon 30th celebration upc"], "match": ["30th collection", "30th etb"],
    "note": "", "source": "https://example.com/source",
}


class TestRules(unittest.TestCase):
    def test_hints(self):
        self.assertIn("한정판", RULES.hint_labels("Canmake Limited Edition"))
        self.assertIn("콜라보", RULES.hint_labels("Ronnie Fieg x ASICS Gel-Lyte III"))
        self.assertIn("품귀", RULES.hint_labels("coming in clutch tackling scalpers"))

    def test_year_is_not_model_number(self):
        self.assertNotIn("모델명", RULES.hint_labels("August 2024 Costco"))
        self.assertIn("모델명", RULES.hint_labels("Hunter Century 90017 Vintage Style Fan"))

    def test_brand_word_boundary(self):
        self.assertEqual(RULES.brand_of("New IVE album"), "ive")
        self.assertIsNone(RULES.brand_of("I give up"))  # give 안의 ive는 무시

    def test_negative(self):
        self.assertTrue(RULES.is_negative("[Routine Help] Malar Bags?"))
        self.assertFalse(RULES.is_negative("Canmake Limited Edition"))


class TestMakeQuery(unittest.TestCase):
    def test_picks_product_sentence(self):
        q = make_query("Cheat code for a good day. Ronnie Fieg x ASICS Gel-Lyte III Remastered “Salmon Toe”", RULES)
        self.assertTrue(q.startswith("Ronnie Fieg x ASICS"))

    def test_adds_brand_when_missing(self):
        q = make_query("Girls' Generation - 2027 Season's Greetings: Twenty in Frost (Teaser Image)", RULES)
        self.assertIn("girls generation", q.lower())  # 검색어에서는 따옴표 제거
        self.assertIn("Season", q)

    def test_removes_tags_stopwords_and_possessive(self):
        q = make_query("[OoT] The Legend of Zelda: Ocarina of Time late-night store openings", RULES)
        self.assertNotIn("OoT", q)
        self.assertNotIn("The ", q)
        self.assertEqual(make_query("TWICE's new album", RULES).split()[0], "TWICE")


class TestLinks(unittest.TestCase):
    def test_links(self):
        links = make_links("canmake limited edition")
        self.assertIn("LH_Sold=1", links["ebay_sold"])
        self.assertIn("LH_Complete=1", links["ebay_sold"])
        self.assertIn("search.shopping.naver.com", links["naver"])
        self.assertIn("canmake limited edition", unquote_plus(links["ebay_active"]))

    def test_norm_key_ignores_order_and_case(self):
        self.assertEqual(norm_key("Limited Canmake"), norm_key("canmake limited!"))


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.result = build(
            trends={"ok": True, "count": 2, "items": [
                trend("weather los angeles", 100),
                trend("labubu restock", 20000),
            ]},
            reddit={"ok": True, "count": 4, "items": [
                reddit_post("Daughter pulled this from the 30th collection", rank=2, hot=0.9),
                reddit_post("Canmake Limited Edition", sub="AsianBeauty"),
                reddit_post("[Routine Help] Malar Bags?", sub="AsianBeauty", rank=2),
                reddit_post("Free Talk Friday!", sub="kpop"),
            ]},
            events={"ok": True, "count": 1, "items": [EVENT]},
            scoring_cfg=SCORING,
            sources_cfg=SOURCES,
        )
        self.by_title = {c["title"]: c for c in self.result["candidates"]}

    def test_non_product_trend_goes_to_others(self):
        self.assertNotIn("weather los angeles", self.by_title)
        self.assertIn("weather los angeles", [o["keyword"] for o in self.result["other_trends"]])

    def test_product_trend_is_candidate(self):
        self.assertIn("labubu restock", self.by_title)

    def test_low_signal_reddit_posts_dropped(self):
        self.assertNotIn("[Routine Help] Malar Bags?", self.by_title)
        self.assertNotIn("Free Talk Friday!", self.by_title)

    def test_cross_match_boosts_both(self):
        ev = self.by_title["Pokemon 30th Celebration UPC"]
        post = self.by_title["Daughter pulled this from the 30th collection"]
        self.assertIn("reddit", ev["sources"])
        self.assertTrue(any("이벤트와 연결" in r for r in post["reasons"]))
        self.assertTrue(any("다른 소스에서 1건" in r for r in ev["reasons"]))

    def test_category_from_group(self):
        self.assertEqual(self.by_title["Canmake Limited Edition"]["category"], "kculture")
        self.assertEqual(self.by_title["Canmake Limited Edition"]["category_label"], "K-컬처")

    def test_output_shape(self):
        c = self.result["candidates"][0]
        for key in ("id", "title", "query", "score", "reasons", "sources", "evidence", "links"):
            self.assertIn(key, c)
        self.assertTrue(0 <= c["score"] <= 100)
        self.assertFalse(any(k.startswith("_") for k in c))  # 내부용 필드는 저장하지 않음
        scores = [c["score"] for c in self.result["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_failed_source_still_builds(self):
        result = build(
            trends={"ok": False, "count": 0, "error": "HTTP 403", "items": []},
            reddit={"ok": True, "count": 1, "items": [reddit_post("Canmake Limited Edition", sub="AsianBeauty")]},
            events={"ok": True, "count": 0, "items": []},
            scoring_cfg=SCORING, sources_cfg=SOURCES,
        )
        self.assertFalse(result["sources"]["google_trends"]["ok"])
        self.assertEqual(len(result["candidates"]), 1)


class TestRealFalsePositives(unittest.TestCase):
    """실제 자동 수집에서 나온 오탐 사례를 다시 생기지 않게 고정한다."""

    def test_lisa_cook_is_not_blackpink_lisa(self):
        # 2026-10-10: 미국 연준 이사 "lisa cook" 검색어가 LISA 컴백 이벤트와 매칭돼 57점 후보가 됐음
        events_cfg = load_yaml("events.yaml")
        lisa = next(e for e in events_cfg["once"] if e["name"].startswith("LISA"))
        event = {**EVENT, "name": lisa["name"], "category": "kpop", "match": lisa["match"], "keywords": lisa["keywords"]}
        result = build(
            trends={"ok": True, "count": 1, "items": [
                trend("lisa cook", 2000, news=["Fed governor Lisa Cook testifies before Senate"]),
            ]},
            reddit={"ok": True, "count": 0, "items": []},
            events={"ok": True, "count": 1, "items": [event]},
            scoring_cfg=SCORING, sources_cfg=SOURCES,
        )
        titles = [c["title"] for c in result["candidates"]]
        self.assertNotIn("lisa cook", titles)
        self.assertIn("lisa cook", [o["keyword"] for o in result["other_trends"]])


if __name__ == "__main__":
    unittest.main()
