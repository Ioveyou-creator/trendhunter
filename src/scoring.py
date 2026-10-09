"""점수화 & 후보 선정.

docs/data/ 의 수집 결과(trends.json, reddit.json, events.json)를 합쳐
"오늘의 후보" 목록(latest.json)을 만든다.

흐름
  1. 각 소스의 항목을 후보로 변환하고 점수를 매긴다
       - Reddit 글: 제목 속 상품 신호(한정판, 콜라보, 품귀, 출시, 개봉...) + 브랜드 - 질문글
       - Google Trends: 검색량 + 상품 신호. 상품 신호가 없으면 후보가 아닌 "기타 급상승"으로 분리
       - 이벤트: 준비 상태(지금 준비 / 준비 예정)와 남은 날짜
  2. 이벤트가 Reddit/Trends에서도 언급되면 양쪽에 가산점 (여러 소스에서 겹치는 신호가 가장 강함)
  3. 같은 검색어로 모이는 후보는 하나로 합친다
  4. 후보마다 eBay 판매완료 / eBay 판매중 / 네이버쇼핑 검색 링크를 붙인다

모든 점수 기준은 config/scoring.yaml 에 있다.

실행:
    python -m src.scoring
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from urllib.parse import quote_plus

from src.config import load_sources, load_yaml
from src.utils import DATA_DIR, now_iso, save_json, setup_console

CATEGORY_LABEL = {
    "shopping": "쇼핑",
    "collectibles": "수집품",
    "kculture": "K-컬처",
    "gaming": "게임",
    "trend": "검색 급상승",
    "season": "시즌",
    "kpop": "K-pop",
    "tcg": "TCG",
    "game": "게임",
    "etc": "기타",
}


# ---------------------------------------------------------------------------
# 설정 / 텍스트 도구
# ---------------------------------------------------------------------------

class Rules:
    """scoring.yaml 을 읽어 정규식으로 미리 컴파일해 둔다."""

    def __init__(self, cfg: dict):
        self.w = cfg.get("weights", {})
        self.min_score = cfg.get("min_score", 35)
        self.top_n = cfg.get("top_n", 30)
        self.hints = [(re.compile(h["pattern"], re.I), h["label"]) for h in cfg.get("product_hints", [])]
        self.brands = [(re.compile(r"\b" + re.escape(b) + r"\b", re.I), b) for b in cfg.get("brands", [])]
        self.negatives = [re.compile(p, re.I) for p in cfg.get("negative_hints", [])]
        self.stopwords = set((cfg.get("stopwords") or "").split())

    def hint_labels(self, text: str) -> list[str]:
        labels = []
        for rx, label in self.hints:
            if rx.search(text) and label not in labels:
                labels.append(label)
        return labels

    def brand_of(self, text: str) -> str | None:
        for rx, name in self.brands:
            if rx.search(text):
                return name
        return None

    def is_negative(self, text: str) -> bool:
        return any(rx.search(text) for rx in self.negatives)


def word_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(str(term).lower()) + r"(?![a-z0-9])", re.I)


EMOJI_AND_SYMBOLS = re.compile(r"[^\w\s'&+.\-]", re.UNICODE)


def make_query(title: str, rules: Rules, max_words: int = 6) -> str:
    """Reddit 제목(문장)에서 eBay 검색에 쓸 핵심어를 뽑는다.

    1. [태그], (괄호) 제거
    2. 문장 단위로 나눠 상품 신호가 가장 많은 문장을 고른다 (같으면 브랜드가 있는 쪽)
       예) "Cheat code for a good day. Ronnie Fieg x ASICS Gel-Lyte III" → 뒤 문장
    3. 고른 문장에 브랜드가 없으면 제목 속 브랜드를 앞에 붙인다
       예) "Girls' Generation - 2027 Season's Greetings" → "girls generation 2027 Season Greetings"
    4. 기호·소유격('s)·불용어를 지우고 앞에서부터 max_words 단어
    """
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", title)
    segments = [s for s in re.split(r"(?<=[.!?:|])\s+|\s[–—-]\s", t) if s.strip()] or [t]

    def strength(seg: str) -> tuple:
        return (len(rules.hint_labels(seg)), 1 if rules.brand_of(seg) else 0)

    best = max(segments, key=strength)
    brand = rules.brand_of(title)
    if brand and not rules.brand_of(best):
        best = f"{brand} {best}"

    best = EMOJI_AND_SYMBOLS.sub(" ", best)
    words = [re.sub(r"['’]s$", "", w).strip(".'’-&+") for w in best.split()]
    words = [w for w in words if w and w.lower() not in rules.stopwords]
    return " ".join(words[:max_words])


def norm_key(query: str) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9가-힣 ]", " ", query.lower()).split()))


def make_links(query: str) -> dict:
    q = quote_plus(query)
    return {
        # 판매완료 + 최근 종료순: 실제로 팔리고 있는지 확인
        "ebay_sold": f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1&_sop=13",
        # 현재 판매중: 경쟁 리스팅 수 확인
        "ebay_active": f"https://www.ebay.com/sch/i.html?_nkw={q}",
        # 국내 소싱 가능 여부
        "naver": f"https://search.shopping.naver.com/search/all?query={q}",
    }


def make_id(query: str) -> str:
    return hashlib.md5(norm_key(query).encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------------------
# 소스별 후보 변환
# ---------------------------------------------------------------------------

def _common_signals(text: str, rules: Rules, score: float, reasons: list[str]) -> float:
    """상품 신호 / 브랜드 / 감점을 점수와 이유 목록에 반영."""
    w = rules.w
    hints = rules.hint_labels(text)
    if hints:
        score += min(len(hints), 3) * w.get("hint", 15)
        reasons.append("상품 신호: " + ", ".join(hints))
    brand = rules.brand_of(text)
    if brand:
        score += w.get("brand", 15)
        reasons.append(f"브랜드/IP: {brand}")
    if rules.is_negative(text):
        score -= w.get("negative", 25)
        reasons.append("질문·후기성 글 (감점)")
    return score


def reddit_candidates(reddit: dict, rules: Rules, sub_group: dict) -> list[dict]:
    out = []
    for p in reddit.get("items", []):
        title = p.get("title", "")
        reasons = [f"r/{p['subreddit']} hot #{p.get('rank', '?')}"]
        score = rules.w.get("reddit_hot", 15) * float(p.get("hot_score", 0))
        score = _common_signals(title, rules, score, reasons)
        query = make_query(title, rules)
        if not query:
            continue
        out.append(
            {
                "title": title,
                "query": query,
                "category": sub_group.get(p["subreddit"].lower(), "etc"),
                "score": score,
                "reasons": reasons,
                "sources": ["reddit"],
                "evidence": [{"source": "reddit", "text": title, "url": p.get("url", "")}],
                "_text": title,
            }
        )
    return out


def trends_candidates(trends: dict, rules: Rules) -> list[dict]:
    w = rules.w
    cap = math.log10(max(w.get("traffic_cap", 20000), 10))
    out = []
    for t in trends.get("items", []):
        kw = t.get("keyword", "")
        traffic = max(int(t.get("traffic", 0)), 1)
        reasons = [f"미국 검색 급상승 {t.get('traffic_label', '')}"]
        score = w.get("trends_traffic", 35) * min(1.0, math.log10(traffic) / cap)
        news_titles = " ".join(n.get("title", "") for n in t.get("news", []))
        # 키워드 자체 + 관련 뉴스 제목까지 보고 상품 신호 판단
        score = _common_signals(f"{kw} {news_titles}", rules, score, reasons)
        evidence = [{"source": "google_trends", "text": f"{kw} ({t.get('traffic_label', '')})", "url": ""}]
        for n in t.get("news", [])[:2]:
            evidence.append({"source": "news", "text": n.get("title", ""), "url": n.get("url", "")})
        out.append(
            {
                "title": kw,
                "query": kw,
                "category": "trend",
                "score": score,
                "reasons": reasons,
                "sources": ["google_trends"],
                "evidence": evidence,
                "_text": kw,
                "_has_product_signal": any(r.startswith(("상품 신호", "브랜드")) for r in reasons),
            }
        )
    return out


def event_candidates(events: dict, rules: Rules, lookahead: int = 60) -> list[dict]:
    w = rules.w
    status_label = {"prepare_now": "지금 준비할 때", "upcoming": "준비 예정", "too_late": "배송 시간 부족"}
    out = []
    for e in events.get("items", []):
        if e["status"] == "prepare_now":
            score = w.get("event_prepare_now", 65)
        elif e["status"] == "upcoming":
            score = w.get("event_upcoming", 40) + 15 * max(0.0, 1 - e["days_left"] / max(lookahead, 1))
        else:
            score = w.get("event_too_late", 20)
        query = (e.get("keywords") or [e["name"]])[0]
        out.append(
            {
                "title": e["name"],
                "query": query,
                "category": e.get("category", "etc"),
                "score": score,
                "reasons": [f"이벤트 D-{e['days_left']} ({e['date']}), {status_label[e['status']]}"],
                "sources": ["events"],
                "evidence": [{"source": "events", "text": e.get("note") or e["name"], "url": e.get("source", "")}],
                "event": {k: e[k] for k in ("date", "days_left", "prep_by", "status")},
                "_match": [word_re(m) for m in (e.get("match") or [])],
            }
        )
    return out


# ---------------------------------------------------------------------------
# 교차 매칭 / 병합 / 마무리
# ---------------------------------------------------------------------------

def cross_match(event_cands: list[dict], other_cands: list[dict], rules: Rules) -> None:
    """이벤트의 match 단어가 Reddit 제목/Trends 키워드에 나오면 양쪽 모두 가산점."""
    w = rules.w
    for ev in event_cands:
        hits = 0
        for c in other_cands:
            if any(rx.search(c["_text"]) for rx in ev["_match"]):
                c["score"] += w.get("event_match", 20)
                c["reasons"].append(f"다가오는 이벤트와 연결: {ev['title']} (D-{ev['event']['days_left']})")
                c["_has_product_signal"] = True
                if hits < 3:
                    ev["score"] += w.get("cross_source", 10)
                    ev["evidence"].append({"source": c["sources"][0], "text": c["title"], "url": c["evidence"][0]["url"]})
                hits += 1
                for s in c["sources"]:
                    if s not in ev["sources"]:
                        ev["sources"].append(s)
        if hits:
            ev["reasons"].append(f"다른 소스에서 {hits}건 언급")


def merge(cands: list[dict]) -> list[dict]:
    """검색어가 같은 후보는 하나로 합친다 (점수는 높은 쪽 + 소스 추가분 보너스)."""
    merged: dict[str, dict] = {}
    for c in sorted(cands, key=lambda x: x["score"], reverse=True):
        key = norm_key(c["query"])
        if key not in merged:
            merged[key] = c
            continue
        m = merged[key]
        for s in c["sources"]:
            if s not in m["sources"]:
                m["sources"].append(s)
                m["score"] += 5
        m["evidence"].extend(c["evidence"])
        for r in c["reasons"]:
            if r not in m["reasons"]:
                m["reasons"].append(r)
    return list(merged.values())


def finalize(c: dict) -> dict:
    c = {k: v for k, v in c.items() if not k.startswith("_")}
    c["score"] = int(round(max(0, min(100, c["score"]))))
    c["id"] = make_id(c["query"])
    c["category_label"] = CATEGORY_LABEL.get(c["category"], c["category"])
    c["links"] = make_links(c["query"])
    c["evidence"] = c["evidence"][:5]
    return c


def build(trends: dict, reddit: dict, events: dict, scoring_cfg: dict, sources_cfg: dict) -> dict:
    """세 소스를 합쳐 latest.json 내용을 만든다 (네트워크·파일 접근 없음 → 테스트 가능)."""
    rules = Rules(scoring_cfg)
    sub_group = {
        sub.lower(): group
        for group, subs in (sources_cfg.get("reddit", {}).get("groups") or {}).items()
        for sub in subs
    }

    r_cands = reddit_candidates(reddit, rules, sub_group)
    t_cands = trends_candidates(trends, rules)
    e_cands = event_candidates(events, rules)
    cross_match(e_cands, r_cands + t_cands, rules)

    # 상품 신호가 없거나 점수 미달인 Trends 키워드는 버리지 않고 "기타 급상승"으로 분리
    def is_trend_candidate(t: dict) -> bool:
        return bool(t.get("_has_product_signal")) and t["score"] >= rules.min_score

    others = [t for t in t_cands if not is_trend_candidate(t)]
    t_cands = [t for t in t_cands if is_trend_candidate(t)]

    pool = [c for c in r_cands + t_cands if c["score"] >= rules.min_score] + e_cands
    candidates = sorted(merge(pool), key=lambda x: x["score"], reverse=True)[: rules.top_n]

    def status(src: dict) -> dict:
        return {k: src.get(k) for k in ("ok", "count", "error", "fetched_at")}

    return {
        "generated_at": now_iso(),
        "sources": {"google_trends": status(trends), "reddit": status(reddit), "events": status(events)},
        "candidates": [finalize(c) for c in candidates],
        "events": events.get("items", []),
        "other_trends": [
            {"keyword": t["title"], "traffic_label": t["evidence"][0]["text"].split("(")[-1].rstrip(")"),
             "links": make_links(t["query"])}
            for t in others
        ],
    }


def _load(name: str) -> dict:
    """수집 결과 파일을 읽는다. 없거나 깨졌으면 '실패한 소스'로 취급."""
    path = DATA_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ok": False, "count": 0, "error": f"{name} 없음 (수집기를 먼저 실행)", "items": []}
    except Exception as e:
        return {"ok": False, "count": 0, "error": f"{name}: {type(e).__name__}", "items": []}


def main() -> None:
    setup_console()
    result = build(
        trends=_load("trends.json"),
        reddit=_load("reddit.json"),
        events=_load("events.json"),
        scoring_cfg=load_yaml("scoring.yaml"),
        sources_cfg=load_sources(),
    )
    path = save_json(result, "latest.json")

    print(f"[scoring] 후보 {len(result['candidates'])}개, 기타 급상승 {len(result['other_trends'])}개 → {path}")
    for name, s in result["sources"].items():
        mark = "OK " if s["ok"] else "실패"
        print(f"  [{mark}] {name}: {s['count']}개" + (f" ({s['error']})" if s["error"] else ""))
    print()
    for i, c in enumerate(result["candidates"][:15], start=1):
        print(f"  {i:>2}. [{c['score']:>3}] ({c['category_label']}) {c['title'][:55]}")
        print(f"       검색어: {c['query']}  |  {c['reasons'][-1] if len(c['reasons']) > 1 else c['reasons'][0]}")


if __name__ == "__main__":
    main()
