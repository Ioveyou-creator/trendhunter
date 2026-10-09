"""이벤트 캘린더.

config/events.yaml 에 적힌 이벤트 중 앞으로 N일 안에 있는 것을 뽑고,
"언제부터 준비해야 하는지"를 계산한다.

  prep_by  = 이벤트 날짜 - lead_days  (이 날부터 소싱·리스팅 시작)
  status
    prepare_now   오늘이 준비 시작일을 지남 → 지금 준비해야 함
    upcoming      아직 준비 시작 전
    too_late      이벤트까지 배송 기간(shipping_days)보다 적게 남음

실행:
    python -m src.collectors.events
    python -m src.collectors.events --today 2026-11-01   # 특정 날짜 기준으로 보기
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date, timedelta

from src.config import load_yaml
from src.utils import save_json, setup_console, source_result

SOURCE = "events"
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def nth_weekday(year: int, month: int, n: int, weekday: str) -> date:
    """year년 month월의 n번째 weekday 날짜. 예) 2026년 11월 넷째 목요일."""
    wd = WEEKDAYS[weekday.lower()]
    first = date(year, month, 1)
    shift = (wd - first.weekday()) % 7
    d = first + timedelta(days=shift + 7 * (n - 1))
    if d.month != month:
        raise ValueError(f"{year}-{month}에는 {n}번째 {weekday}가 없음")
    return d


def expand(cfg: dict, today: date) -> list[dict]:
    """설정의 세 가지 형식(yearly / nth_weekday / once)을 실제 날짜 목록으로 펼친다.
    매년 반복 이벤트는 올해와 내년 날짜를 모두 만든다 (연말에 내년 2월 이벤트를 보기 위해)."""
    events = []

    def add(e: dict, d: date, kind: str) -> None:
        events.append({**{k: v for k, v in e.items() if k not in ("date", "month", "n", "weekday", "offset_days")},
                       "date": d, "kind": kind})

    for year in (today.year, today.year + 1):
        for e in cfg.get("yearly", []) or []:
            month, day = (int(x) for x in str(e["date"]).split("-"))
            if month == 2 and day == 29 and not calendar.isleap(year):
                continue
            add(e, date(year, month, day), "yearly")
        for e in cfg.get("nth_weekday", []) or []:
            d = nth_weekday(year, int(e["month"]), int(e["n"]), e["weekday"])
            add(e, d + timedelta(days=int(e.get("offset_days", 0))), "nth_weekday")

    for e in cfg.get("once", []) or []:
        add(e, date.fromisoformat(str(e["date"])), "once")

    return events


def upcoming(cfg: dict, today: date) -> list[dict]:
    """오늘부터 lookahead_days 안의 이벤트를 날짜순으로, 준비 상태와 함께 반환."""
    lookahead = int(cfg.get("lookahead_days", 60))
    default_lead = int(cfg.get("default_lead_days", 21))
    shipping = int(cfg.get("shipping_days", 10))
    end = today + timedelta(days=lookahead)

    result = []
    for e in expand(cfg, today):
        d = e["date"]
        if not (today <= d <= end):
            continue
        lead = int(e.get("lead_days", default_lead))
        days_left = (d - today).days
        prep_by = d - timedelta(days=lead)

        # K-pop처럼 준비 기간이 배송 기간보다 짧은 이벤트(한국 발매 당일 구매)는 배송 경고 대상이 아님
        if lead > shipping and days_left < shipping:
            status = "too_late"
        elif today >= prep_by:
            status = "prepare_now"
        else:
            status = "upcoming"

        result.append(
            {
                "name": e["name"],
                "category": e.get("category", "etc"),
                "date": d.isoformat(),
                "days_left": days_left,
                "prep_by": prep_by.isoformat(),
                "lead_days": lead,
                "status": status,
                "keywords": e.get("keywords", []),
                "note": e.get("note", ""),
                "source": e.get("source", ""),
                "kind": e["kind"],
            }
        )

    result.sort(key=lambda x: (x["date"], x["name"]))
    return result


def collect(today: date | None = None, cfg: dict | None = None) -> dict:
    today = today or date.today()
    try:
        cfg = cfg if cfg is not None else load_yaml("events.yaml")
        result = source_result(SOURCE, upcoming(cfg, today))
    except Exception as e:  # 설정 파일 오타 등
        result = source_result(SOURCE, [], error=f"{type(e).__name__}: {e}")
    result["today"] = today.isoformat()
    return result


STATUS_LABEL = {"prepare_now": "지금 준비", "upcoming": "준비 예정", "too_late": "배송 부족"}


def main() -> None:
    setup_console()
    parser = argparse.ArgumentParser(description="다가오는 이벤트 추출")
    parser.add_argument("--today", help="기준 날짜 YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    result = collect(today=today)
    path = save_json(result, "events.json")

    if result["ok"]:
        print(f"[events] {result['today']} 기준 {result['count']}개 이벤트 → {path}")
        for e in result["items"]:
            print(f"  {e['date']}  D-{e['days_left']:<3} [{STATUS_LABEL[e['status']]}] {e['name']}")
    else:
        print(f"[events] 실패: {result['error']}")


if __name__ == "__main__":
    main()
