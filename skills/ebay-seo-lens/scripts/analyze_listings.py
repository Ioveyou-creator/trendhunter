"""eBay 완료 리스팅 '답안지' 분석기.

같은 상품을 eBay에서 검색해 '완료된 리스팅'을 보면 팔린 것과 안 팔린 것이 함께 나온다.
이 스크립트는 그 결과를 표로 정리하고, 팔린 것과 안 팔린 것을 가르는 요인 후보를 숫자로 비교한다.
어떤 요인이 '핵심 변수'인지 고르는 판단은 하지 않는다 (그건 SKILL.md 절차에 따라 사람/AI가 한다).

입력 형식 (자동 판별)
  1) eBay 검색 결과 페이지를 복사해 붙여넣은 텍스트 (.txt)
     - "Sold  Oct 28, 2026" 줄이 있으면 팔림, "Ended Oct 28, 2026"이 있으면 안 팔림으로 본다
  2) CSV (.csv): title, price, shipping, status 열. status는 sold 또는 unsold

사용법
  python analyze_listings.py 입력파일 [--json 결과.json]

표준 라이브러리만 사용. Python 3.7에서도 돌아가도록 := 같은 3.8+ 문법은 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
from pathlib import Path

STATUS_RE = re.compile(r"^\s*(Sold|Ended)\s+([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*$")
PRICE_RE = re.compile(r"^\s*(?:US\s*)?\$\s?([\d,]+(?:\.\d{1,2})?)(?:\s+to\s+\$[\d,.]+)?\s*$")
SHIP_RE = re.compile(r"^\s*\+?\s*(?:US\s*)?\$\s?([\d,]+(?:\.\d{1,2})?)\s+(?:shipping|delivery|postage)", re.I)
FREE_SHIP_RE = re.compile(r"^\s*free\s+(?:international\s+)?(?:shipping|delivery|postage)", re.I)
NOISE_RE = re.compile(
    r"^\s*(opens in a new window or tab|shop on ebay|sponsored|new listing|watch|"
    r"\d+\s+watchers?|\d+\s+sold|top rated plus|authenticity guarantee|"
    r"see similar items?|sell one like this|.*\bfeedback\b.*)\s*$",
    re.I,
)
CONDITION_RE = re.compile(r"^\s*(brand new|new|pre-owned|used|open box|refurbished|for parts.*)(\s*\|.*)?\s*$", re.I)
LOCATION_RE = re.compile(r"^\s*(?:located in|from)\s+(.+?)\s*$", re.I)
BEST_OFFER_RE = re.compile(r"best offer", re.I)
AUCTION_RE = re.compile(r"^\s*\d+\s+bids?\b", re.I)

STOPWORDS = set(
    "a an the and or of for with to in on by from new brand ver version item items lot set "
    "us usa free shipping fast ship".split()
)
MIN_SUPPORT = 3  # 키워드가 최소 이만큼의 리스팅에 나와야 비교 대상으로 삼음


# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------

def parse_text(text: str) -> tuple[list[dict], list[str]]:
    """eBay 결과 페이지 복사 텍스트 → 리스팅 목록, 인식 못 한 줄 목록.

    상태 줄(Sold/Ended 날짜)을 리스팅의 시작으로 보고, 다음 상태 줄 전까지를 한 리스팅으로 묶는다.
    상태 줄 다음에 나오는 첫 '의미 있는 줄'을 제목으로 본다.
    """
    listings: list[dict] = []
    unparsed: list[str] = []
    cur: dict | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = STATUS_RE.match(line)
        if m:
            cur = {
                "title": None, "price": None, "shipping": None, "status": "sold" if m.group(1) == "Sold" else "unsold",
                "date": m.group(2), "condition": None, "location": None, "best_offer": False, "auction": False,
            }
            listings.append(cur)
            continue
        if cur is None:
            continue  # 첫 리스팅 이전의 줄은 검색창, 필터, 메뉴라서 무시
        if NOISE_RE.match(line):
            continue
        if cur["title"] is None:
            cur["title"] = line
            continue
        price_m, ship_m, loc_m = PRICE_RE.match(line), SHIP_RE.match(line), LOCATION_RE.match(line)
        if price_m and cur["price"] is None:
            cur["price"] = float(price_m.group(1).replace(",", ""))
        elif ship_m:
            cur["shipping"] = float(ship_m.group(1).replace(",", ""))
        elif FREE_SHIP_RE.match(line):
            cur["shipping"] = 0.0
        elif loc_m:
            cur["location"] = loc_m.group(1)
        elif CONDITION_RE.match(line):
            cur["condition"] = line.split("|")[0].strip()
        elif BEST_OFFER_RE.search(line):
            cur["best_offer"] = True
        elif AUCTION_RE.match(line):
            cur["auction"] = True
        else:
            unparsed.append(line)

    listings = [l for l in listings if l["title"]]
    return listings, unparsed


def parse_csv(text: str) -> tuple[list[dict], list[str]]:
    """CSV(title, price, shipping, status[, location, condition]) → 리스팅 목록."""
    listings, unparsed = [], []
    reader = csv.DictReader(io.StringIO(text))
    fields = {f.lower().strip(): f for f in (reader.fieldnames or [])}
    for row in reader:
        r = {k.lower().strip(): (v or "").strip() for k, v in row.items() if k}
        status = r.get("status", "").lower()
        if status not in ("sold", "unsold") or not r.get("title"):
            unparsed.append(",".join(row.values()))
            continue

        def num(v: str) -> float | None:
            v = v.replace("$", "").replace(",", "").strip()
            if v.lower() in ("free", "0", "0.0", "0.00"):
                return 0.0
            try:
                return float(v)
            except ValueError:
                return None

        listings.append({
            "title": r["title"], "price": num(r.get("price", "")), "shipping": num(r.get("shipping", "")),
            "status": status, "date": r.get("date") or None, "condition": r.get("condition") or None,
            "location": r.get("location") or None, "best_offer": "offer" in r.get("format", "").lower(),
            "auction": "auction" in r.get("format", "").lower(),
        })
    if "title" not in fields or "status" not in fields:
        unparsed.insert(0, "CSV에 title, status 열이 필요합니다")
    return listings, unparsed


def parse(text: str, filename: str = "") -> tuple[list[dict], list[str], str]:
    first = text.lstrip().splitlines()[0].lower() if text.strip() else ""
    if filename.lower().endswith(".csv") or ("title" in first and "status" in first and "," in first):
        return (*parse_csv(text), "csv")
    return (*parse_text(text), "ebay_text")


# ---------------------------------------------------------------------------
# 비교
# ---------------------------------------------------------------------------

def tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", title.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    grams = set(words)
    grams.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return grams


def rate(items: list[dict]) -> float | None:
    return round(sum(1 for i in items if i["status"] == "sold") / len(items), 3) if items else None


def compare_feature(listings: list[dict], name: str, has) -> dict:
    """특징이 있는 리스팅과 없는 리스팅의 판매율 비교."""
    yes = [l for l in listings if has(l)]
    no = [l for l in listings if not has(l)]
    ry, rn = rate(yes), rate(no)
    return {
        "feature": name,
        "with": {"n": len(yes), "sold": sum(l["status"] == "sold" for l in yes), "sell_through": ry},
        "without": {"n": len(no), "sold": sum(l["status"] == "sold" for l in no), "sell_through": rn},
        "gap": round(ry - rn, 3) if ry is not None and rn is not None else None,
    }


def median(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 2) if vals else None


def analyze(listings: list[dict]) -> dict:
    sold = [l for l in listings if l["status"] == "sold"]
    unsold = [l for l in listings if l["status"] == "unsold"]

    def total(l: dict) -> float | None:
        return None if l["price"] is None else l["price"] + (l["shipping"] or 0.0)

    price_known = [l for l in listings if l["price"] is not None]
    med_total = median([total(l) for l in price_known])

    features = [
        compare_feature(listings, "무료 배송", lambda l: l["shipping"] == 0.0),
        compare_feature(listings, "가격 제안(Best Offer) 가능", lambda l: l["best_offer"]),
        compare_feature(listings, "경매 형식", lambda l: l["auction"]),
        compare_feature(listings, "한국 발송", lambda l: bool(l["location"]) and "korea" in l["location"].lower()),
        compare_feature(listings, "총액(가격+배송)이 중앙값 이하",
                        lambda l: med_total is not None and total(l) is not None and total(l) <= med_total),
        compare_feature(listings, "제목 60자 이상", lambda l: len(l["title"]) >= 60),
    ]
    features = [f for f in features if f["with"]["n"] and f["without"]["n"]]  # 한쪽이 0이면 비교 불가

    # 제목 키워드: 키워드가 들어간 리스팅의 판매율 - 안 들어간 리스팅의 판매율
    vocab: dict[str, int] = {}
    for l in listings:
        for t in tokens(l["title"]):
            vocab[t] = vocab.get(t, 0) + 1
    keywords = []
    for term, n in vocab.items():
        if n < MIN_SUPPORT:  # 너무 드문 단어는 우연일 가능성이 커서 제외 (모든 리스팅에 나온 단어는 비교 불가라 아래서 걸러짐)
            continue
        c = compare_feature(listings, term, lambda l, t=term: t in tokens(l["title"]))
        if c["gap"] is not None:
            keywords.append(c)
    keywords.sort(key=lambda c: (-abs(c["gap"]), -c["with"]["n"]))

    return {
        "counts": {"total": len(listings), "sold": len(sold), "unsold": len(unsold),
                   "sell_through": rate(listings)},
        "small_sample": len(sold) < 5 or len(unsold) < 5,
        "price": {
            "median_price_sold": median([l["price"] for l in sold]),
            "median_price_unsold": median([l["price"] for l in unsold]),
            "median_total_sold": median([total(l) for l in sold]),
            "median_total_unsold": median([total(l) for l in unsold]),
        },
        "features": sorted(features, key=lambda f: -abs(f["gap"] or 0)),
        "keywords_top": keywords[:12],
    }


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def pct(v) -> str:
    return "-" if v is None else f"{v * 100:.0f}%"


def to_markdown(listings: list[dict], unparsed: list[str], fmt: str, result: dict) -> str:
    c = result["counts"]
    out = [
        "# 답안지 분석 결과",
        "",
        f"- 입력 형식: {fmt}",
        f"- 리스팅 {c['total']}개 = 팔림 {c['sold']}개 + 안 팔림 {c['unsold']}개 (전체 판매율 {pct(c['sell_through'])})",
    ]
    if result["small_sample"]:
        out.append("- ⚠️ 표본이 작습니다 (팔림 또는 안 팔림이 5개 미만). 아래 차이는 우연일 수 있습니다.")
    if unparsed:
        out.append(f"- 인식하지 못한 줄 {len(unparsed)}개 (아래 목록 참고)")

    p = result["price"]
    out += [
        "",
        "## 가격",
        "",
        "| | 팔림 | 안 팔림 |",
        "|---|---|---|",
        f"| 가격 중앙값 | {p['median_price_sold']} | {p['median_price_unsold']} |",
        f"| 총액(가격+배송) 중앙값 | {p['median_total_sold']} | {p['median_total_unsold']} |",
        "",
        "## 리스팅 조건별 판매율",
        "",
        "| 조건 | 있음: 판매율 (n) | 없음: 판매율 (n) | 차이 |",
        "|---|---|---|---|",
    ]
    for f in result["features"]:
        out.append(f"| {f['feature']} | {pct(f['with']['sell_through'])} ({f['with']['n']}) | "
                   f"{pct(f['without']['sell_through'])} ({f['without']['n']}) | {pct(f['gap'])} |")
    out += [
        "",
        f"## 제목 키워드별 판매율 (최소 {MIN_SUPPORT}개 리스팅에 나온 단어, 차이 큰 순)",
        "",
        "| 키워드 | 들어감: 판매율 (n) | 빠짐: 판매율 (n) | 차이 |",
        "|---|---|---|---|",
    ]
    for k in result["keywords_top"]:
        out.append(f"| {k['feature']} | {pct(k['with']['sell_through'])} ({k['with']['n']}) | "
                   f"{pct(k['without']['sell_through'])} ({k['without']['n']}) | {pct(k['gap'])} |")
    out += ["", "## 리스팅 목록", "", "| 상태 | 가격 | 배송 | 제목 |", "|---|---|---|---|"]
    for l in listings:
        ship = "-" if l["shipping"] is None else ("무료" if l["shipping"] == 0 else l["shipping"])
        out.append(f"| {'팔림' if l['status'] == 'sold' else '안 팔림'} | {l['price']} | {ship} | {l['title']} |")
    if unparsed:
        out += ["", "## 인식하지 못한 줄", ""] + [f"- {u}" for u in unparsed[:30]]
    return "\n".join(out)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="eBay 완료 리스팅 답안지 분석")
    ap.add_argument("input", help="eBay 결과 붙여넣기 텍스트(.txt) 또는 CSV")
    ap.add_argument("--json", help="분석 결과를 JSON으로도 저장할 경로")
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    listings, unparsed, fmt = parse(text, args.input)
    if not listings:
        print("리스팅을 하나도 인식하지 못했습니다. 'Sold 날짜' 또는 'Ended 날짜' 줄이 포함되도록 복사했는지, "
              "또는 CSV에 title,price,shipping,status 열이 있는지 확인하세요.")
        if unparsed:
            print("\n인식하지 못한 줄 (처음 10개):\n" + "\n".join(unparsed[:10]))
        sys.exit(1)

    result = analyze(listings)
    print(to_markdown(listings, unparsed, fmt, result))
    if args.json:
        Path(args.json).write_text(json.dumps({"format": fmt, "listings": listings, "unparsed": unparsed, **result},
                                              ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
