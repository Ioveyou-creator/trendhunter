"""급상승 추적 테스트. 실제 파일 대신 임시 폴더 사용."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.history import annotate, load_past, save_snapshot, snapshot


def result(*ids, day="2026-10-09"):
    """id 순서대로 순위가 매겨진 가짜 점수화 결과."""
    return {"date": day, "candidates": [{"id": i, "title": i.upper(), "query": i, "score": 50} for i in ids]}


def snap(day, *ids):
    return snapshot(result(*ids, day=day), date.fromisoformat(day))


class TestAnnotate(unittest.TestCase):
    def test_first_run(self):
        r = annotate(result("a", "b"), past=[])
        self.assertEqual(r["candidates"][0]["trend"]["status"], "first_run")
        self.assertIsNone(r["history"]["previous_date"])
        self.assertEqual(r["dropped"], [])

    def test_new_up_down_same(self):
        # 어제: a b c d e  → 오늘: d x c a e  (b는 빠짐, x는 새로 등장)
        r = annotate(result("d", "x", "c", "a", "e"), past=[snap("2026-10-08", "a", "b", "c", "d", "e")])
        t = {c["id"]: c["trend"] for c in r["candidates"]}
        self.assertEqual(t["d"]["status"], "up")      # 4위 → 1위 (+3)
        self.assertEqual(t["d"]["rank_change"], 3)
        self.assertEqual(t["a"]["status"], "down")    # 1위 → 4위 (-3)
        self.assertEqual(t["x"]["status"], "new")
        self.assertIsNone(t["x"]["prev_rank"])
        self.assertEqual(t["c"]["status"], "same")    # 3위 → 3위
        self.assertEqual([c["id"] for c in r["dropped"]], ["b"])
        self.assertEqual(r["history"]["new_count"], 1)

    def test_small_moves_are_same(self):
        # 새 후보가 끼어들어 1~2칸 밀린 것은 변동으로 표시하지 않음
        r = annotate(result("x", "y", "a", "b"), past=[snap("2026-10-08", "a", "b")])
        t = {c["id"]: c["trend"] for c in r["candidates"]}
        self.assertEqual(t["a"]["status"], "same")
        self.assertEqual(t["a"]["rank_change"], -2)   # 숫자는 그대로 기록

    def test_streak_counts_consecutive_days(self):
        past = [
            snap("2026-10-08", "a", "b"),
            snap("2026-10-07", "a", "b"),
            snap("2026-10-06", "a"),
        ]
        r = annotate(result("a", "b", "c"), past)
        t = {c["id"]: c["trend"]["streak"] for c in r["candidates"]}
        self.assertEqual(t, {"a": 4, "b": 3, "c": 1})

    def test_streak_stops_at_missing_day(self):
        # 10-07 기록이 없으면(수집 실패 등) 연속이 끊긴 것으로 본다
        past = [snap("2026-10-08", "a"), snap("2026-10-06", "a")]
        r = annotate(result("a"), past)
        self.assertEqual(r["candidates"][0]["trend"]["streak"], 2)

    def test_compares_with_latest_past_even_if_gap(self):
        # 이틀 전 기록이 마지막이어도 비교는 그 기록과 한다
        r = annotate(result("a", "x"), past=[snap("2026-10-07", "a")])
        self.assertEqual(r["history"]["previous_date"], "2026-10-07")
        self.assertEqual(r["candidates"][1]["trend"]["status"], "new")


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_past_excludes_today_and_sorts(self):
        for d, ids in [("2026-10-07", "a"), ("2026-10-08", "b"), ("2026-10-09", "c")]:
            save_snapshot(result(ids, day=d), date.fromisoformat(d), folder=self.dir)
        past = load_past(date(2026, 10, 9), folder=self.dir)
        self.assertEqual([p["date"] for p in past], ["2026-10-08", "2026-10-07"])

    def test_same_day_rerun_overwrites(self):
        save_snapshot(result("a"), date(2026, 10, 9), folder=self.dir)
        save_snapshot(result("a", "b"), date(2026, 10, 9), folder=self.dir)
        files = list(self.dir.glob("????-??-??.json"))
        self.assertEqual(len(files), 1)
        saved = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(len(saved["candidates"]), 2)

    def test_old_files_cleaned_and_index_written(self):
        save_snapshot(result("a", day="2026-08-01"), date(2026, 8, 1), folder=self.dir)
        save_snapshot(result("a"), date(2026, 10, 9), folder=self.dir, keep_days=60)
        self.assertFalse((self.dir / "2026-08-01.json").exists())
        index = json.loads((self.dir / "index.json").read_text())
        self.assertEqual(index["dates"], ["2026-10-09"])

    def test_broken_file_is_skipped(self):
        (self.dir / "2026-10-08.json").write_text("{broken", encoding="utf-8")
        save_snapshot(result("a", day="2026-10-07"), date(2026, 10, 7), folder=self.dir)
        past = load_past(date(2026, 10, 9), folder=self.dir)
        self.assertEqual([p["date"] for p in past], ["2026-10-07"])


if __name__ == "__main__":
    unittest.main()
