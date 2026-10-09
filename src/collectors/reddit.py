"""Reddit 수집기.

config/sources.yaml 에 적힌 서브레딧 그룹에서 지금 뜨는 글을 가져온다.

수정 이력 (실제로 돌려보며 바꾼 것)
  v1  서브레딧마다 JSON 요청 → 비로그인 JSON 전부 차단
  v2  서브레딧마다 RSS 요청 + 6초 간격 → 14개 중 4개만 성공 (HTTP 429 요청 한도)
  v3  서브레딧을 그룹으로 묶어 "r/a+b+c/hot/.rss" 한 번에 요청 (현재)
      - 요청 수 14번 → 그룹 수(4번)로 감소
      - 그룹 요청이 실패하면 그 그룹만 서브레딧별로 다시 시도

점수: RSS에는 업보트 수가 없으므로 "서브레딧 안에서의 hot 순위"를 쓴다.
  hot_score = 1 - (순위-1)/해당 서브레딧 글 수   → 1위 1.0

실행:
    python -m src.collectors.reddit
    python -m src.collectors.reddit --file tests/fixtures/reddit_sample.xml
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

from src.config import load_sources
from src.utils import http_get, save_json, setup_console, source_result

SOURCE = "reddit"
RSS_URL = "https://www.reddit.com/r/{subs}/{sort}/.rss?limit={limit}"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
SUB_IN_URL = re.compile(r"/r/([^/]+)/", re.IGNORECASE)

DEFAULT_DELAY = 10.0  # 요청 사이 대기 시간(초)
RETRY_WAIT = 30.0     # 429를 받았을 때 기다릴 시간(초)


def hot_score(rank: int, total: int) -> float:
    """hot 순위를 0~1 점수로 변환. rank는 1부터 시작."""
    if total <= 0:
        return 0.0
    return round(1 - (rank - 1) / total, 3)


def error_label(e: Exception) -> str:
    """예외를 사람이 읽기 쉬운 짧은 문자열로."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    return type(e).__name__


def is_excluded(title: str, patterns: list[str]) -> bool:
    """공지·정기 스레드 등 제외 대상 제목인지."""
    return any(re.search(p, title, re.IGNORECASE) for p in patterns)


def _subreddit_of(entry: ET.Element) -> str:
    """글이 속한 서브레딧 이름. <category term>을 먼저 보고, 없으면 링크 URL에서 추출."""
    cat = entry.find("a:category", ATOM)
    if cat is not None and cat.get("term"):
        return cat.get("term")
    link = entry.find("a:link", ATOM)
    m = SUB_IN_URL.search(link.get("href", "")) if link is not None else None
    return m.group(1) if m else ""


def parse_rss(
    xml_bytes: bytes,
    exclude: list[str] | None = None,
    keep_top: int = 10,
    now: float | None = None,
) -> list[dict]:
    """여러 서브레딧이 섞인 RSS(Atom)를 파싱.

    피드 순서가 hot 순위이므로, 서브레딧별로 나눈 뒤 각 서브레딧 안에서 순위를 매긴다.
    """
    now = now or time.time()
    exclude = exclude or []
    root = ET.fromstring(xml_bytes)

    by_sub: dict[str, list[dict]] = {}
    for entry in root.findall("a:entry", ATOM):
        title = (entry.findtext("a:title", "", ATOM) or "").strip()
        if not title or is_excluded(title, exclude):
            continue
        sub = _subreddit_of(entry)
        link_el = entry.find("a:link", ATOM)
        published = entry.findtext("a:published", "", ATOM) or entry.findtext("a:updated", "", ATOM)
        try:
            ts = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()
        except ValueError:
            ts = now
        by_sub.setdefault(sub.lower(), []).append(
            {
                "title": title,
                "subreddit": sub,
                "age_hours": round((now - ts) / 3600, 1),
                "url": link_el.get("href", "") if link_el is not None else "",
            }
        )

    posts = []
    for sub_posts in by_sub.values():
        total = len(sub_posts)
        for rank, p in enumerate(sub_posts[:keep_top], start=1):
            p["rank"] = rank
            p["hot_score"] = hot_score(rank, total)
            posts.append(p)
    return posts


def _get_with_retry(url: str) -> bytes:
    """429(요청 과다)를 받으면 한 번 기다렸다가 재시도."""
    try:
        return http_get(url)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        wait = RETRY_WAIT
        retry_after = e.headers.get("Retry-After") if e.headers else None
        if retry_after and retry_after.isdigit():
            wait = min(float(retry_after), 90.0)
        print(f"    요청 한도 초과, {int(wait)}초 대기 후 재시도")
        time.sleep(wait)
        return http_get(url)


def fetch_group(subs: list[str], cfg: dict) -> bytes:
    url = RSS_URL.format(subs="+".join(subs), sort=cfg.get("sort", "hot"), limit=cfg.get("limit", 100))
    return _get_with_retry(url)


def collect(file: str | None = None) -> dict:
    """모든 그룹을 수집. 일부가 실패해도 나머지 결과는 살린다."""
    cfg = load_sources().get("reddit", {})
    keep_top = cfg.get("keep_top", 10)
    exclude = cfg.get("exclude_title_patterns", [])
    delay = float(cfg.get("request_delay", DEFAULT_DELAY))

    if file:  # 테스트용: 저장된 RSS 파일 하나를 읽음
        try:
            with open(file, "rb") as f:
                posts = parse_rss(f.read(), exclude, keep_top)
            return source_result(SOURCE, posts)
        except Exception as e:
            return source_result(SOURCE, [], error=f"{type(e).__name__}: {e}")

    groups: dict = cfg.get("groups", {})
    all_posts, failed = [], []
    first = True

    def wait():
        nonlocal first
        if not first:
            time.sleep(delay)
        first = False

    for name, subs in groups.items():
        wait()
        try:
            posts = parse_rss(fetch_group(subs, cfg), exclude, keep_top)
            all_posts.extend(posts)
            got = sorted({p["subreddit"].lower() for p in posts})
            missing = [s for s in subs if s.lower() not in got]
            print(f"  [{name}] {len(posts)}개 글 ({len(got)}/{len(subs)}개 서브레딧)")
            if missing:
                print(f"    글이 없는 서브레딧: {', '.join(missing)}")
        except Exception as e:
            # 그룹 요청 실패(예: 그룹 안에 폐쇄된 서브레딧) → 서브레딧별로 재시도
            print(f"  [{name}] 그룹 요청 실패 ({error_label(e)}), 서브레딧별로 재시도")
            for sub in subs:
                wait()
                try:
                    posts = parse_rss(fetch_group([sub], cfg), exclude, keep_top)
                    all_posts.extend(posts)
                    print(f"    r/{sub}: {len(posts)}개")
                except Exception as e2:
                    failed.append(f"r/{sub}: {error_label(e2)}")
                    print(f"    r/{sub}: 실패 ({error_label(e2)})")

    all_posts.sort(key=lambda x: x["hot_score"], reverse=True)
    error = None
    if failed and not all_posts:
        error = "모든 서브레딧 실패: " + ", ".join(failed)
    result = source_result(SOURCE, all_posts, error=error)
    result["failed"] = failed
    return result


def main() -> None:
    setup_console()
    parser = argparse.ArgumentParser(description="Reddit 급상승 글 수집")
    parser.add_argument("--file", help="네트워크 대신 사용할 로컬 RSS(XML) 파일")
    args = parser.parse_args()

    if not args.file:
        groups = load_sources().get("reddit", {}).get("groups", {})
        n = sum(len(v) for v in groups.values())
        print(f"[reddit] {len(groups)}개 그룹, {n}개 서브레딧 수집 시작")

    result = collect(file=args.file)
    path = save_json(result, "reddit.json")

    if result["ok"]:
        ok_subs = len({p["subreddit"].lower() for p in result["items"]})
        print(f"[reddit] {ok_subs}개 서브레딧, {result['count']}개 글 수집 → {path}")
        if result.get("failed"):
            print(f"  실패: {', '.join(result['failed'])}")
        for p in result["items"][:12]:
            print(f"  #{p['rank']:<2} r/{p['subreddit']:<20} {p['title'][:60]}")
    else:
        print(f"[reddit] 실패: {result['error']}")


if __name__ == "__main__":
    main()
