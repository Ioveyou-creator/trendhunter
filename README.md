# TrendHunter

> eBay 해외 판매자를 위한 "오늘 터질 상품" 자동 발굴 대시보드 (바이브 코딩 과제)

🚧 개발 중입니다. 진행 상황은 [TODO.md](TODO.md)를 확인하세요.

**대시보드: https://ioveyou-creator.github.io/trendhunter/**

## 한 줄 소개

Google Trends, Reddit, 이벤트 캘린더에서 매일 신호를 자동 수집해 점수를 매기고, eBay 판매완료 검색으로 바로 검증할 수 있는 후보 상품 목록을 보여줍니다. GitHub Actions와 GitHub Pages만 사용해 **비용 0원**으로 운영합니다.

## 실행 방법

Python 3.7 이상이 필요합니다.

```bash
# 1. 의존성 설치 (처음 한 번)
python -m pip install -r requirements.txt

# 2. 테스트 (인터넷 없이 샘플 데이터로 실행)
python -m unittest discover tests

# 3. 전체 실행 (수집 3종 + 점수화, 약 1분) → docs/data/latest.json
python -m src.run_all

# 단계별로 따로 실행할 때
python -m src.collectors.google_trends
python -m src.collectors.reddit
python -m src.collectors.events
python -m src.scoring              # 점수화 + 급상승 추적(전날 대비 NEW/▲▼)

# 4. 대시보드 보기 → 브라우저에서 http://localhost:8000
python -m http.server -d docs
```

`docs/index.html`을 더블클릭해서 열면 브라우저 보안 정책 때문에 데이터를 읽지 못합니다. 위처럼 간단한 서버로 열어 주세요.

## 자동 실행

GitHub Actions가 매일 한국 시간 오전 7시 17분에 수집을 돌리고, 결과(`docs/data/`)를 저장소에 자동으로 커밋합니다. GitHub Pages가 `docs/` 폴더를 웹사이트로 보여주므로 대시보드도 자동으로 갱신됩니다. 설정은 [.github/workflows/daily.yml](.github/workflows/daily.yml)에 있습니다.

로봇이 매일 커밋하므로, 내 PC에서 작업하기 전에는 항상 `git pull`을 먼저 실행하세요.

## 문서

- [PRD.md](PRD.md): 제품 요구사항
- [TODO.md](TODO.md): 단계별 작업 목록
- [DEVLOG.md](DEVLOG.md): 바이브 코딩 개발 기록

## 리뷰

> 개발 완료 후 작성 예정: 제작한 것 소개 / 방법론의 장단점 / 개선이 필요한 점 / 결론
