"""전체 파이프라인을 한 번에 실행: 수집 3종 → 점수화.

실행:
    python -m src.run_all

GitHub Actions(7단계)에서도 이 명령 하나로 매일 실행한다.
한 수집기가 실패해도 나머지는 계속 진행하고, 실패한 소스는 latest.json 에 상태로 남는다.
"""

from __future__ import annotations

import sys
import time

from src import scoring
from src.collectors import events, google_trends, reddit
from src.utils import setup_console

STEPS = [
    ("Google Trends", google_trends.main),
    ("Reddit", reddit.main),
    ("이벤트 캘린더", events.main),
    ("점수화", scoring.main),
]


def main() -> None:
    setup_console()
    start = time.time()
    for i, (name, fn) in enumerate(STEPS, start=1):
        print(f"\n===== [{i}/{len(STEPS)}] {name} =====")
        # 각 수집기는 자체 argparse를 쓰므로, 이 스크립트의 인자가 넘어가지 않게 비워 둔다
        sys.argv = [sys.argv[0]]
        try:
            fn()
        except Exception as e:  # 예상 못 한 오류가 나도 다음 단계는 진행
            print(f"[{name}] 예기치 못한 오류: {type(e).__name__}: {e}")
    print(f"\n완료 ({time.time() - start:.0f}초). 결과: docs/data/latest.json")


if __name__ == "__main__":
    main()
