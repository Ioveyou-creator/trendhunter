/*
 * eBay 완료 리스팅 "답안지" 파서 + 비교 계산 (브라우저용)
 *
 * skills/ebay-seo-lens/scripts/analyze_listings.py 와 같은 규칙으로 동작한다.
 * 두 구현이 같은 결과를 내는지는 tests/test_parser_parity.py 가 확인한다.
 *
 * - 네트워크를 쓰지 않는다. 붙여넣은 데이터는 브라우저 밖으로 나가지 않는다.
 * - 브라우저에서는 window.ListingParser, Node에서는 module.exports 로 쓴다.
 */
(function (root) {
  "use strict";

  const MONEY = String.raw`(?:US\s*)?(\$|₩|KRW\s?)\s?([\d,]+(?:\.\d{1,2})?)`;

  const STATUS_RE = new RegExp(
    String.raw`^\s*(Sold|Ended|판매됨|종료됨)\s+` +
    String.raw`([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일)\s*$`
  );
  const SOLD_WORDS = ["Sold", "판매됨"];
  const PRICE_RE = new RegExp(String.raw`^\s*` + MONEY + String.raw`(?:\s+to\s+.+|\s*·\s*.+)?\s*$`);
  const SHIP_RE = new RegExp(
    String.raw`^\s*\+?\s*(?:` + MONEY + String.raw`\s+(?:shipping|delivery|postage)|배송비\s*` + MONEY + ")",
    "i"
  );
  const FREE_SHIP_RE = /^\s*(free\s+(international\s+)?(shipping|delivery|postage)|무료\s*(국제\s*)?배송)/i;
  const NOISE_RE = new RegExp(
    String.raw`^\s*(opens in a new window or tab|shop on ebay|sponsored|new listing|watch|` +
    String.raw`\d+\s+watchers?|\d+\s+sold|top rated plus|authenticity guarantee|free returns|` +
    String.raw`see similar items?|sell one like this|.*\bfeedback\b.*|` +
    String.raw`이와 비슷한 상품 판매|무료 반품|[★☆\s]+\(\d+\)|#.*)\s*$`,
    "i"
  );
  const CONDITION_RE = new RegExp(
    String.raw`^\s*(brand new|new|pre-owned|used|open box|refurbished|for parts.*|` +
    String.raw`사전 소유 상품|중고|새 상품.*|완전 새 상품|개봉 상품|리퍼.*|부품용.*)(\s*\|.*)?\s*$`,
    "i"
  );
  const LOCATION_RE = /^\s*(?:located in|from|출발지)\s+(.+?)\s*$/i;
  const OFFER_ACCEPTED_RE = /best offer accepted|베스트 오퍼 수락됨/i;
  const BEST_OFFER_RE = /best offer|베스트 오퍼/i;
  const BUY_NOW_RE = /^\s*(or buy it now|buy it now|또는 즉시 구매|즉시 구매)\s*$/i;
  const BIDS_RE = /^\s*(\d+)\s+bids?\b|^\s*입찰\s*(\d+)\s*건/i;

  const STOPWORDS = new Set(
    ("a an the and or of for with to in on by from new brand ver version item items lot set " +
      "us usa free shipping fast ship").split(" ")
  );
  const MIN_SUPPORT = 3;

  function money(m, offset) {
    const sym = m[1 + offset].trim();
    return [parseFloat(m[2 + offset].replace(/,/g, "")), sym === "$" ? "USD" : "KRW"];
  }

  // ------------------------------------------------------------------ 파싱

  function parseText(text) {
    const listings = [];
    const unparsed = [];
    let cur = null;

    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line) continue;
      const st = STATUS_RE.exec(line);
      if (st) {
        cur = {
          title: null, price: null, shipping: null, currency: null,
          status: SOLD_WORDS.includes(st[1]) ? "sold" : "unsold",
          date: st[2], condition: null, location: null,
          best_offer: false, offer_accepted: false, auction: false, bids: null,
        };
        listings.push(cur);
        continue;
      }
      if (cur === null) continue; // 첫 리스팅 이전 줄(검색창, 필터)은 무시
      if (NOISE_RE.test(line)) continue;
      if (cur.title === null) { cur.title = line; continue; }

      const pm = PRICE_RE.exec(line), sm = SHIP_RE.exec(line), lm = LOCATION_RE.exec(line), bm = BIDS_RE.exec(line);
      if (pm && cur.price === null) {
        [cur.price, cur.currency] = money(pm, 0);
      } else if (sm) {
        [cur.shipping, cur.currency] = money(sm, sm[1] ? 0 : 2);
      } else if (FREE_SHIP_RE.test(line)) {
        cur.shipping = 0;
      } else if (lm) {
        cur.location = lm[1];
      } else if (CONDITION_RE.test(line)) {
        cur.condition = line.split("|")[0].trim();
      } else if (OFFER_ACCEPTED_RE.test(line)) {
        cur.best_offer = cur.offer_accepted = true;
      } else if (BEST_OFFER_RE.test(line)) {
        cur.best_offer = true;
      } else if (bm) {
        cur.auction = true;
        cur.bids = parseInt(bm[1] || bm[2], 10);
      } else if (BUY_NOW_RE.test(line)) {
        // 형식 정보일 뿐이라 저장하지 않음
      } else {
        unparsed.push(line);
      }
    }
    return { listings: listings.filter((l) => l.title), unparsed };
  }

  // 따옴표 안 쉼표를 처리하는 작은 CSV 파서
  function csvRows(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (ch === '"') quoted = false;
        else field += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(field); field = ""; }
      else if (ch === "\n" || ch === "\r") {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        row.push(field); rows.push(row); row = []; field = "";
      } else field += ch;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    return rows.filter((r) => r.some((c) => c.trim() !== ""));
  }

  function parseCsv(text) {
    const rows = csvRows(text);
    const listings = [], unparsed = [];
    if (!rows.length) return { listings, unparsed: ["CSV에 title, status 열이 필요합니다"] };
    const head = rows[0].map((h) => h.trim().toLowerCase());
    const col = (r, name) => { const i = head.indexOf(name); return i >= 0 ? (r[i] || "").trim() : ""; };
    const num = (v) => {
      v = v.replace(/(US\s*)?\$|₩|KRW/g, "").replace(/,/g, "").trim();
      if (["free", "무료", "0", "0.0", "0.00"].includes(v.toLowerCase())) return 0;
      const n = parseFloat(v);
      return Number.isFinite(n) && /^[\d.]+$/.test(v) ? n : null;
    };
    for (const r of rows.slice(1)) {
      const rawStatus = col(r, "status");
      const status = { "판매됨": "sold", "종료됨": "unsold" }[rawStatus] || rawStatus.toLowerCase();
      if (!["sold", "unsold"].includes(status) || !col(r, "title")) { unparsed.push(r.join(",")); continue; }
      const rawPrice = col(r, "price"), fmt = col(r, "format").toLowerCase();
      listings.push({
        title: col(r, "title"), price: num(rawPrice), shipping: num(col(r, "shipping")),
        currency: rawPrice.includes("₩") || rawPrice.includes("KRW") ? "KRW" : (col(r, "currency") || "USD"),
        status, date: col(r, "date") || null, condition: col(r, "condition") || null,
        location: col(r, "location") || null, best_offer: fmt.includes("offer"),
        offer_accepted: fmt.includes("accepted"), auction: fmt.includes("auction"), bids: null,
      });
    }
    if (!head.includes("title") || !head.includes("status")) unparsed.unshift("CSV에 title, status 열이 필요합니다");
    return { listings, unparsed };
  }

  function parse(text, filename) {
    const first = text.trim() ? text.trimStart().split(/\r?\n/)[0].toLowerCase() : "";
    const isCsv = (filename || "").toLowerCase().endsWith(".csv") ||
      (first.includes("title") && first.includes("status") && first.includes(","));
    const r = isCsv ? parseCsv(text) : parseText(text);
    return { ...r, format: isCsv ? "csv" : "ebay_text" };
  }

  // ------------------------------------------------------------------ 비교

  const round = (x, d) => Math.round(x * 10 ** d) / 10 ** d;

  function tokens(title) {
    const words = (title.toLowerCase().match(/[a-z0-9]+(?:'[a-z]+)?/g) || [])
      .filter((w) => !STOPWORDS.has(w) && w.length > 1);
    const grams = new Set(words);
    for (let i = 0; i + 1 < words.length; i++) grams.add(words[i] + " " + words[i + 1]);
    return grams;
  }

  function rate(items) {
    return items.length ? round(items.filter((i) => i.status === "sold").length / items.length, 3) : null;
  }

  function compareFeature(listings, name, has) {
    const yes = listings.filter(has), no = listings.filter((l) => !has(l));
    const ry = rate(yes), rn = rate(no);
    return {
      feature: name,
      with: { n: yes.length, sold: yes.filter((l) => l.status === "sold").length, sell_through: ry },
      without: { n: no.length, sold: no.filter((l) => l.status === "sold").length, sell_through: rn },
      gap: ry !== null && rn !== null ? round(ry - rn, 3) : null,
    };
  }

  function median(vals) {
    const v = vals.filter((x) => x !== null && x !== undefined).sort((a, b) => a - b);
    if (!v.length) return null;
    const mid = Math.floor(v.length / 2);
    return round(v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2, 2);
  }

  function analyze(listings) {
    const sold = listings.filter((l) => l.status === "sold");
    const unsold = listings.filter((l) => l.status === "unsold");
    const total = (l) => (l.price === null ? null : l.price + (l.shipping || 0));
    const medTotal = median(listings.filter((l) => l.price !== null).map(total));

    let features = [
      compareFeature(listings, "무료 배송", (l) => l.shipping === 0),
      compareFeature(listings, "가격 제안(Best Offer) 가능", (l) => l.best_offer),
      compareFeature(listings, "경매 형식", (l) => l.auction),
      compareFeature(listings, "한국 발송",
        (l) => !!l.location && (l.location.toLowerCase().includes("korea") || l.location.includes("한국"))),
      compareFeature(listings, "해외 발송지 표시됨", (l) => !!l.location),
      compareFeature(listings, "총액(가격+배송)이 중앙값 이하",
        (l) => medTotal !== null && total(l) !== null && total(l) <= medTotal),
      compareFeature(listings, "제목 60자 이상", (l) => l.title.length >= 60),
    ].filter((f) => f.with.n && f.without.n);
    features.sort((a, b) => Math.abs(b.gap || 0) - Math.abs(a.gap || 0));

    const vocab = new Map();
    for (const l of listings) for (const t of [...tokens(l.title)].sort()) vocab.set(t, (vocab.get(t) || 0) + 1);
    const keywords = [];
    for (const [term, n] of vocab) {
      if (n < MIN_SUPPORT) continue;
      const c = compareFeature(listings, term, (l) => tokens(l.title).has(term));
      if (c.gap !== null) keywords.push(c);
    }
    keywords.sort((a, b) =>
      Math.abs(b.gap) - Math.abs(a.gap) || b.with.n - a.with.n || (a.feature < b.feature ? -1 : a.feature > b.feature ? 1 : 0));

    const currencies = [...new Set(listings.map((l) => l.currency).filter(Boolean))].sort();
    return {
      currency: currencies.length === 1 ? currencies[0] : null,
      mixed_currency: currencies.length > 1,
      missing_price: listings.filter((l) => l.price === null).length,
      counts: { total: listings.length, sold: sold.length, unsold: unsold.length, sell_through: rate(listings) },
      small_sample: sold.length < 5 || unsold.length < 5,
      price: {
        median_price_sold: median(sold.map((l) => l.price)),
        median_price_unsold: median(unsold.map((l) => l.price)),
        median_total_sold: median(sold.map(total)),
        median_total_unsold: median(unsold.map(total)),
      },
      features,
      keywords_top: keywords.slice(0, 12),
    };
  }

  const api = { parse, parseText, parseCsv, analyze, tokens, MIN_SUPPORT };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ListingParser = api;
})(typeof window !== "undefined" ? window : globalThis);
