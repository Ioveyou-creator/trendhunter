"""이벤트 캘린더 테스트 (실제 config 대신 테스트용 설정 사용)."""

import unittest
from datetime import date

from src.collectors.events import collect, nth_weekday, upcoming

CFG = {
    "lookahead_days": 60,
    "default_lead_days": 21,
    "shipping_days": 10,
    "yearly": [
        {"name": "Halloween", "date": "10-31"},
        {"name": "Valentine", "date": "02-14"},
    ],
    "nth_weekday": [
        {"name": "Black Friday", "month": 11, "n": 4, "weekday": "thu", "offset_days": 1},
    ],
    "once": [
        {"name": "Comeback", "date": "2026-10-12", "lead_days": 3, "category": "kpop"},
        {"name": "Past event", "date": "2026-10-01"},
    ],
}


class TestNthWeekday(unittest.TestCase):
    def test_thanksgiving(self):
        # 미국 추수감사절: 2026-11-26, 2027-11-25
        self.assertEqual(nth_weekday(2026, 11, 4, "thu"), date(2026, 11, 26))
        self.assertEqual(nth_weekday(2027, 11, 4, "thu"), date(2027, 11, 25))

    def test_mothers_day(self):
        self.assertEqual(nth_weekday(2027, 5, 2, "sun"), date(2027, 5, 9))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            nth_weekday(2026, 2, 5, "mon")  # 2026년 2월에는 다섯째 월요일이 없음


class TestUpcoming(unittest.TestCase):
    def setUp(self):
        self.events = {e["name"]: e for e in upcoming(CFG, date(2026, 10, 9))}

    def test_window(self):
        self.assertNotIn("Past event", self.events)   # 지난 이벤트 제외
        self.assertNotIn("Valentine", self.events)    # 60일 밖
        self.assertIn("Black Friday", self.events)

    def test_black_friday_date(self):
        self.assertEqual(self.events["Black Friday"]["date"], "2026-11-27")
        self.assertEqual(self.events["Black Friday"]["days_left"], 49)

    def test_status(self):
        # 핼러윈 D-22, 준비 21일 → 아직 준비 시작 전
        self.assertEqual(self.events["Halloween"]["status"], "upcoming")
        # 컴백 D-3, 준비 3일 → 지금 준비 (K-pop은 배송 경고 대상 아님)
        self.assertEqual(self.events["Comeback"]["status"], "prepare_now")

    def test_too_late(self):
        events = {e["name"]: e for e in upcoming(CFG, date(2026, 10, 25))}
        # 핼러윈 D-6, 배송 10일 → 늦음
        self.assertEqual(events["Halloween"]["status"], "too_late")

    def test_next_year_events_appear_in_december(self):
        events = {e["name"]: e for e in upcoming(CFG, date(2026, 12, 20))}
        self.assertEqual(events["Valentine"]["date"], "2027-02-14")


class TestCollect(unittest.TestCase):
    def test_bad_config_does_not_raise(self):
        result = collect(today=date(2026, 10, 9), cfg={"once": [{"name": "x", "date": "not-a-date"}]})
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
