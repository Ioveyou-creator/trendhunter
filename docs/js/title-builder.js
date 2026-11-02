/*
 * eBay 리스팅 제목 빌더 (브라우저 / Node 공용)
 *
 * 규칙 출처: skills/ebay-seo-lens/references/ebay-title-rules.md
 * - 최대 80자. 중요한 단어를 앞에.
 * - 실제 상품과 관련된 단어만, 대문자 남용·장식·반복 피하기.
 * - 키워드는 답안지(팔린 리스팅 제목)에 실제로 나온 단어에서 가져온다.
 */
(function (root) {
  "use strict";

  const MAX_LEN = 80;

  // 앞에 올수록 중요. 80자를 넘으면 뒤에서부터 뺀다 (브랜드와 상품명은 빼지 않음)
  const PARTS = [
    { key: "brand", label: "브랜드/IP", keep: true },
    { key: "name", label: "상품명", keep: true },
    { key: "number", label: "번호/버전" },
    { key: "feature", label: "핵심 특징" },
    { key: "condition", label: "상태" },
    { key: "region", label: "언어/지역" },
    { key: "extra", label: "추가 키워드" },
  ];

  const clean = (s) => String(s || "").replace(/\s+/g, " ").trim();

  /** 칸별 입력 → 제목. 앞 칸에 이미 나온 단어는 뒤에서 다시 쓰지 않는다 */
  function assemble(segments) {
    const seen = new Set();
    const words = [];
    for (const seg of segments) {
      for (const w of seg.text.split(" ")) {
        const k = w.toLowerCase().replace(/[^\p{L}\p{N}#/.+-]/gu, "");
        if (!w || (k && seen.has(k))) continue;
        if (k) seen.add(k);
        words.push(w);
      }
    }
    return words.join(" ");
  }

  function buildTitle(parts, max) {
    max = max || MAX_LEN;
    let segs = [];
    for (const p of PARTS) {
      const vals = p.key === "extra" ? (parts.extra || []) : [parts[p.key]];
      for (const v of vals) {
        const text = clean(v);
        if (text) segs.push({ key: p.key, label: p.label, keep: !!p.keep, text });
      }
    }
    const dropped = [];
    let title = assemble(segs);
    // 80자를 넘으면 중요도가 낮은 칸(뒤쪽)부터 하나씩 뺀다
    while (title.length > max) {
      let i = segs.length - 1;
      while (i >= 0 && segs[i].keep) i--;
      if (i < 0) break;
      dropped.unshift(segs[i]);
      segs = segs.slice(0, i).concat(segs.slice(i + 1));
      title = assemble(segs);
    }
    let truncated = false;
    if (title.length > max) {
      // 브랜드+상품명만으로도 넘치면 단어 단위로 자른다
      const cut = title.slice(0, max + 1);
      title = cut.lastIndexOf(" ") > 0 ? cut.slice(0, cut.lastIndexOf(" ")) : title.slice(0, max);
      truncated = true;
    }
    return { title, length: title.length, dropped, truncated };
  }

  /** 제목 점검. level: error(등록 불가) / warn(검색에 불리할 수 있음) / ok */
  function checkTitle(title, max) {
    max = max || MAX_LEN;
    const t = clean(title);
    const out = [];
    if (!t) return [{ level: "error", code: "empty", msg: "제목이 비어 있습니다." }];

    if (t.length > max) out.push({ level: "error", code: "too_long", msg: `${t.length}자입니다. eBay 제목은 최대 ${max}자라 등록되지 않습니다.` });
    else if (t.length < 50) out.push({ level: "warn", code: "short", msg: `${t.length}자입니다. ${max}자까지 쓸 수 있으니 구매자가 검색할 단어를 더 넣을 여유가 있습니다.` });
    else out.push({ level: "ok", code: "length", msg: `${t.length}/${max}자` });

    const words = t.split(" ");
    // NM, PSA, ETB, TCG 같은 짧은 약어나 숫자가 섞인 코드는 대문자여도 괜찮다
    const longWords = words.filter((w) => /[A-Za-z]{4,}/.test(w) && !/\d/.test(w));
    const caps = longWords.filter((w) => w === w.toUpperCase());
    if (longWords.length >= 3 && caps.length / longWords.length > 0.5)
      out.push({ level: "warn", code: "caps", msg: "단어 대부분이 대문자입니다. 읽기 어렵고 스팸처럼 보일 수 있습니다." });

    if (/l@@k|\bwow\b|!{2,}|\*{2,}|\bmust see\b|\bnr\b|\bhot\b/i.test(t))
      out.push({ level: "warn", code: "decoration", msg: "L@@K, WOW, !!! 같은 장식은 검색에 도움이 되지 않습니다." });

    const counts = {};
    for (const w of words) {
      const k = w.toLowerCase().replace(/[^a-z0-9]/g, "");
      if (k.length >= 3) counts[k] = (counts[k] || 0) + 1;
    }
    const rep = Object.keys(counts).filter((k) => counts[k] > 1);
    if (rep.length) out.push({ level: "warn", code: "repeat", msg: `같은 단어가 반복됩니다: ${rep.join(", ")}` });

    if (/free\s+ship|무료\s*배송/i.test(t))
      out.push({ level: "warn", code: "shipping", msg: "무료 배송은 eBay 배송 설정으로 표시되므로 제목에 쓰지 않아도 됩니다." });

    if (/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(t))
      out.push({ level: "warn", code: "emoji", msg: "이모지는 검색어로 쓰이지 않고 공간만 차지합니다." });

    return out;
  }

  /**
   * 답안지에서 "팔린 리스팅에 자주 나왔는데 내 제목에 없는 단어"를 찾는다.
   * analyzeResult: ListingParser.analyze() 결과, tokensFn: ListingParser.tokens
   * 조건: 팔린 리스팅 2개 이상에 나오고, 들어간 쪽 판매율이 더 높은 단어
   * 순서: 팔린 리스팅에 많이 나온 순 (차이만 보면 표본이 작은 단어가 앞에 온다)
   * 두 단어 묶음은 빠진 단어가 이미 한 단어 제안에 있으면 중복이라 뺀다
   */
  function suggestKeywords(analyzeResult, title, tokensFn, limit) {
    limit = limit || 8;
    const have = tokensFn(title || "");
    const cands = (analyzeResult.keywords_top || [])
      .filter((k) => k.gap > 0 && k.with.sold >= 2 && !have.has(k.feature))
      .sort((a, b) => b.with.sold - a.with.sold || b.gap - a.gap || (a.feature < b.feature ? -1 : 1));
    const singles = new Set(cands.filter((k) => !k.feature.includes(" ")).map((k) => k.feature));
    return cands
      .filter((k) => {
        if (!k.feature.includes(" ")) return true;
        const missing = k.feature.split(" ").filter((w) => !have.has(w));
        return missing.length > 0 && !missing.every((w) => singles.has(w));
      })
      .slice(0, limit)
      .map((k) => ({ term: k.feature, soldWith: k.with.sold, nWith: k.with.n, gap: k.gap }));
  }

  /** 소문자 키워드를 팔린 리스팅 제목에 실제로 쓰인 모양으로 (photocard → Photocard, pob → POB) */
  function originalCase(term, titles) {
    return term.split(" ").map((w) => {
      const counts = {};
      const re = new RegExp("(^|[^A-Za-z0-9])(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![A-Za-z0-9])", "gi");
      for (const t of titles) { let m; while ((m = re.exec(t))) counts[m[2]] = (counts[m[2]] || 0) + 1; }
      const best = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || (a < b ? -1 : 1))[0];
      return best || w;
    }).join(" ");
  }

  const api = { MAX_LEN, PARTS, buildTitle, checkTitle, suggestKeywords, originalCase };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TitleBuilder = api;
})(typeof window !== "undefined" ? window : globalThis);
