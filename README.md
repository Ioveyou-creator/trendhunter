# TrendHunter

> eBay 해외 판매자를 위한 "오늘 터질 상품" 자동 발굴 대시보드 (바이브 코딩 과제)

🚧 개발 중입니다. 진행 상황은 [TODO.md](TODO.md)를 확인하세요.

## 한 줄 소개

Google Trends, Reddit, 이벤트 캘린더에서 매일 신호를 자동 수집해 점수를 매기고, eBay 판매완료 검색으로 바로 검증할 수 있는 후보 상품 목록을 보여줍니다. GitHub Actions와 GitHub Pages만 사용해 **비용 0원**으로 운영합니다.

## 실행 방법

Python 3.7 이상이 필요합니다.

```bash
# 1. 의존성 설치 (처음 한 번)
pip install -r requirements.txt

# 2. 테스트 (인터넷 없이 샘플 데이터로 실행)
python -m unittest discover tests

# 3. 수집 실행 → 결과는 docs/data/*.json
python -m src.collectors.google_trends
python -m src.collectors.reddit   # 약 30초~1분
```

## 문서

- [PRD.md](PRD.md): 제품 요구사항
- [TODO.md](TODO.md): 단계별 작업 목록
- [DEVLOG.md](DEVLOG.md): 바이브 코딩 개발 기록

## 리뷰

> 개발 완료 후 작성 예정: 제작한 것 소개 / 방법론의 장단점 / 개선이 필요한 점 / 결론
