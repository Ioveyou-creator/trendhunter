# TODO

각 단계가 끝날 때마다 체크하고 push 한다.

## 0단계: 저장소 세팅
- [x] 폴더 구조 생성
- [x] PRD.md 작성
- [x] TODO.md 작성
- [x] DEVLOG.md 작성
- [x] README.md 뼈대
- [x] **push #1**

## 1단계: Google Trends 수집기
- [x] 미국 Trending now RSS 파싱
- [x] 검색량 추정치(approx_traffic) 숫자 변환
- [x] `docs/data/trends.json` 저장
- [x] 실패 시 빈 결과 + 에러 메시지 반환
- [x] 샘플 XML 기반 단위 테스트 (네트워크 없이 실행)
- [x] **push #2**

## 2단계: Reddit 수집기
- [x] 대상 서브레딧 목록 설정 (`config/sources.yaml`)
- [x] hot/rising 글 수집 (공개 JSON)
- [x] JSON 차단 시 RSS로 재시도
- [x] 업보트·댓글 수 기반 신호 추출 (시간당 속도 velocity)
- [x] 공지글·성인글 제외, 일부 서브레딧 실패해도 계속 진행
- [x] 단위 테스트
- [x] 실제 실행 결과 반영: JSON 차단 → RSS 전용, 요청 간격 6초 + 429 재시도, hot 순위 점수
- [x] 실제 실행 결과 반영 2: 서브레딧 그룹 묶음 요청, 폐쇄된 서브레딧 제거, 공지글 필터
- [x] **push #3**

## 3단계: 이벤트 캘린더
- [x] `config/events.yaml` 형식 정의 (매년 고정일 / N번째 요일 / 일회성)
- [x] 실제 일정 입력: 시즌 이벤트, K-pop 컴백 11건, Pokemon TCG 2건 (출처 링크 포함)
- [x] 향후 N일 이내 이벤트 추출
- [x] 준비 시작일(prep_by)과 상태(지금 준비 / 준비 예정 / 배송 부족) 계산
- [x] 단위 테스트
- [x] **push #4**

## 4단계: 점수화 & 후보 선정
- [x] 소스별 점수 정규화 (`config/scoring.yaml`에서 조정)
- [x] 상품성 필터: 제목 속 상품 신호(한정판·콜라보·품귀·출시·개봉 등) + 브랜드, 질문글 감점
- [x] 상품 신호 없는 검색어(날씨·스포츠·인물)는 "기타 급상승"으로 분리
- [x] 이벤트 ↔ Reddit/Trends 교차 매칭 가산점
- [x] Reddit 제목에서 eBay 검색어 추출
- [x] eBay 판매완료 / eBay 판매중 / 네이버쇼핑 검증 링크 생성
- [x] `docs/data/latest.json` 생성
- [x] 전체 실행 명령 `python -m src.run_all`
- [x] 단위 테스트 (실제 수집 제목 사용)
- [ ] **push #5**

## 5단계: 급상승 추적
- [ ] 날짜별 기록 `docs/data/history/` 저장
- [ ] 전날 대비 NEW / 순위 변동 계산
- [ ] **push #6**

## 6단계: 대시보드
- [ ] `docs/index.html` 후보 카드 목록
- [ ] NEW 배지, 소스별 근거, 검증 링크
- [ ] 다가오는 이벤트 섹션
- [ ] 소스 수집 상태 표시
- [ ] **push #7**

## 7단계: 자동화
- [ ] GitHub Actions 워크플로 (매일 실행 + 결과 커밋)
- [ ] GitHub Pages 설정 안내
- [ ] **push #8**

## 8단계: 리뷰 문서 (README)
- [ ] 제작한 것 소개
- [ ] PRD / TODO 요약 링크
- [ ] 방법론(바이브 코딩)의 장단점 — DEVLOG 근거
- [ ] 개선이 필요한 점
- [ ] 결론
- [ ] **push #9 (최종)**
