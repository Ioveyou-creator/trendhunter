"""급상승 추적: 날짜별 기록을 남기고 전날과 비교한다.

  docs/data/history/YYYY-MM-DD.json   그날의 후보 스냅샷 (id, 제목, 점수, 순위)
  docs/data/history/index.json        기록이 있는 날짜 목록 (대시보드에서 사용)

각 후보에 붙는 정보 (candidate["trend"])
  status        new(어제 없음) | up(3칸 이상 상승) | down(3칸 이상 하락) | same | first_run(비교할 기록 없음)
  prev_rank     어제 순위 (없으면 None)
  rank_change   +면 상승 (어제 5위 → 오늘 2위 = +3)
  streak        며칠 연속 후보에 올랐는지 (오늘 포함)

비교 기준은 "오늘보다 이전 날짜 중 가장 최근 기록"이다.
같은 날 여러 번 실행해도 오늘 기록끼리 비교하지 않는다 (오늘 파일은 덮어씀).

날짜는 한국 시간(KST) 기준. Python 3.7에도 있는 고정 오프셋(UTC+9)을 쓴다.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.utils import DATA_DIR

HISTORY_DIR = DATA_DIR / "history"
KST = timezone(timedelta(hours=9))
KEEP_DAYS = 60          # 이보다 오래된 기록 파일은 정리
MIN_RANK_MOVE = 3       # 순위가 이만큼 이상 움직여야 상승/하락으로 표시
                        # (새 후보가 끼어들 때마다 나머지가 전부 ▼1, ▼2 로 표시되는 것을 막기 위해)
STREAK_LOOKBACK = 14    # 연속 일수는 최대 이만큼만 거슬러 올라가 계산


def today_kst() -> date:
    return datetime.now(KST).date()


# ---------------------------------------------------------------------------
# 순수 함수 (파일 접근 없음 → 테스트 쉬움)
# ---------------------------------------------------------------------------

def snapshot(result: dict, day: date) -> dict:
    """latest.json 결과에서 비교에 필요한 최소 정보만 뽑는다."""
    return {
        "date": day.isoformat(),
        "candidates": [
            {"id": c["id"], "title": c["title"], "query": c["query"], "score": c["score"], "rank": i}
            for i, c in enumerate(result.get("candidates", []), start=1)
        ],
    }


def annotate(result: dict, past: list[dict]) -> dict:
    """result의 후보마다 trend 정보를 붙이고, 어제 있다가 빠진 후보 목록을 만든다.

    past: 오늘 이전 스냅샷 목록, 최신 날짜가 앞 (past[0] = 직전 기록)
    """
    prev = past[0] if past else None
    prev_by_id = {c["id"]: c for c in prev["candidates"]} if prev else {}

    # 연속 일수 계산: 날짜가 하루씩 끊김 없이 이어지는 동안만 센다
    consecutive = []
    if prev:
        expected = date.fromisoformat(result_date(result)) - timedelta(days=1)
        for snap in past:
            if date.fromisoformat(snap["date"]) != expected:
                break
            consecutive.append({c["id"] for c in snap["candidates"]})
            expected -= timedelta(days=1)

    for rank, c in enumerate(result.get("candidates", []), start=1):
        streak = 1
        for ids in consecutive:
            if c["id"] not in ids:
                break
            streak += 1

        p = prev_by_id.get(c["id"])
        if prev is None:
            status, prev_rank, change = "first_run", None, 0
        elif p is None:
            status, prev_rank, change = "new", None, 0
        else:
            prev_rank = p["rank"]
            change = prev_rank - rank
            status = "up" if change >= MIN_RANK_MOVE else "down" if change <= -MIN_RANK_MOVE else "same"

        c["trend"] = {"status": status, "prev_rank": prev_rank, "rank_change": change, "streak": streak}

    today_ids = {c["id"] for c in result.get("candidates", [])}
    result["dropped"] = [c for c in (prev["candidates"] if prev else []) if c["id"] not in today_ids]
    result["history"] = {
        "date": result_date(result),
        "previous_date": prev["date"] if prev else None,
        "new_count": sum(1 for c in result.get("candidates", []) if c["trend"]["status"] == "new"),
    }
    return result


def result_date(result: dict) -> str:
    """결과의 기준 날짜(KST). build()가 넣어 둔 값이 없으면 오늘."""
    return result.get("date") or today_kst().isoformat()


# ---------------------------------------------------------------------------
# 파일 입출력
# ---------------------------------------------------------------------------

def load_past(day: date, folder: Path = HISTORY_DIR, limit: int = STREAK_LOOKBACK) -> list[dict]:
    """day 이전 날짜의 스냅샷을 최신순으로 최대 limit개."""
    if not folder.exists():
        return []
    files = sorted(
        (p for p in folder.glob("????-??-??.json") if p.stem < day.isoformat()),
        reverse=True,
    )[:limit]
    past = []
    for p in files:
        try:
            past.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue  # 깨진 파일은 건너뜀
    return past


def save_snapshot(result: dict, day: date, folder: Path = HISTORY_DIR, keep_days: int = KEEP_DAYS) -> Path:
    """오늘 스냅샷 저장 + 오래된 파일 정리 + 날짜 목록(index.json) 갱신."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day.isoformat()}.json"
    path.write_text(json.dumps(snapshot(result, day), ensure_ascii=False, indent=1), encoding="utf-8")

    cutoff = (day - timedelta(days=keep_days)).isoformat()
    for old in folder.glob("????-??-??.json"):
        if old.stem < cutoff:
            old.unlink()

    dates = sorted((p.stem for p in folder.glob("????-??-??.json")), reverse=True)
    (folder / "index.json").write_text(json.dumps({"dates": dates}, indent=1), encoding="utf-8")
    return path


def track(result: dict, day: date | None = None) -> dict:
    """점수화 결과에 급상승 정보를 붙이고 오늘 기록을 저장한다 (scoring.main에서 호출)."""
    day = day or today_kst()
    result["date"] = day.isoformat()
    annotate(result, load_past(day))
    save_snapshot(result, day)
    return result
