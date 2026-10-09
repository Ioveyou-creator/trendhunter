"""Google Trends "Trending now" RSS 수집기.

미국(geo=US)에서 지금 검색량이 급상승 중인 키워드를 가져온다.
API 키가 필요 없는 공개 RSS 피드를 사용한다.

실행:
    python -m src.collectors.google_trends              # 실제 피드 수집
    python -m src.collectors.google_trends --file x.xml # 저장된 XML로 테스트
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET

from src.utils import http_get, save_json, source_result

SOURCE = "google_trends"
FEED_URL = "https://trends.google.com/trending/rss?geo={geo}"
NS = {"ht": "https://trends.google.com/trending/rss"}


def parse_traffic(label: str) -> int:
    """'2000+', '10K+', '1M+' 같은 검색량 표기를 정수로 변환."""
    if not label:
        return 0
    m = re.match(r"([\d,.]+)\s*([KkMm]?)", label.strip())
    if not m:
        return 0
    num = float(m.group(1).replace(",", ""))
    unit = m.group(2).upper()
    if unit == "K":
        num *= 1_000
    elif unit == "M":
        num *= 1_000_000
    return int(num)


def _text(el: ET.Element, path: str) -> str:
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None else ""


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """RSS XML을 파싱해 키워드 목록을 반환 (검색량 내림차순)."""
    root = ET.fromstring(xml_bytes)
    items = []
    seen = set()

    for item in root.iter("item"):
        keyword = _text(item, "title")
        if not keyword:
            continue
        key = keyword.lower()
        if key in seen:  # 같은 키워드 중복 제거
            continue
        seen.add(key)

        traffic_label = _text(item, "ht:approx_traffic")
        news = [
            {
                "title": _text(n, "ht:news_item_title"),
                "url": _text(n, "ht:news_item_url"),
                "source": _text(n, "ht:news_item_source"),
            }
            for n in item.findall("ht:news_item", NS)
        ]

        items.append(
            {
                "keyword": keyword,
                "traffic": parse_traffic(traffic_label),
                "traffic_label": traffic_label,
                "pub_date": _text(item, "pubDate"),
                "picture": _text(item, "ht:picture"),
                "news": news,
            }
        )

    items.sort(key=lambda x: x["traffic"], reverse=True)
    return items


def collect(geo: str = "US", file: str | None = None) -> dict:
    """피드를 수집해 공통 포맷으로 반환. 실패해도 예외 대신 ok=False 결과를 돌려준다."""
    try:
        if file:
            with open(file, "rb") as f:
                xml_bytes = f.read()
        else:
            xml_bytes = http_get(FEED_URL.format(geo=geo))
        return source_result(SOURCE, parse_feed(xml_bytes))
    except Exception as e:  # 네트워크 오류, 파싱 오류 등
        return source_result(SOURCE, [], error=f"{type(e).__name__}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Trends 급상승 검색어 수집")
    parser.add_argument("--geo", default="US", help="국가 코드 (기본: US)")
    parser.add_argument("--file", help="네트워크 대신 사용할 로컬 XML 파일")
    args = parser.parse_args()

    result = collect(geo=args.geo, file=args.file)
    path = save_json(result, "trends.json")

    if result["ok"]:
        print(f"[google_trends] {result['count']}개 수집 → {path}")
        for it in result["items"][:10]:
            print(f"  {it['traffic_label']:>7}  {it['keyword']}")
    else:
        print(f"[google_trends] 실패: {result['error']}")


if __name__ == "__main__":
    main()
