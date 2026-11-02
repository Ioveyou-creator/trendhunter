/*
 * 키워드 기회 점수 계산 (브라우저 / Node 공용)
 *
 * 수요 = 판매완료 수 (eBay에서 Sold items 필터를 켜고 검색했을 때 결과 수, 대략 최근 90일)
 * 경쟁 = 판매중 수   (필터 없이 검색했을 때 결과 수)
 * 기회 비율 = 판매완료 ÷ 판매중
 *
 * 등급 기준(BANDS)은 리셀러들이 흔히 쓰는 대략적인 값이다. 실제 판매로 검증한 기준이 아니므로
 * 화면에도 그렇게 표시하고, 판매 결과가 쌓이면 이 숫자를 고친다.
 */
(function (root) {
  "use strict";

  const BANDS = [
    { min: 1.0, key: "hot", label: "수요가 공급보다 많음", note: "판매중인 리스팅보다 최근 팔린 것이 더 많습니다." },
    { min: 0.5, key: "good", label: "들어갈 틈 있음", note: "판매중 2개당 1개 이상이 최근에 팔렸습니다." },
    { min: 0.2, key: "fair", label: "보통", note: "경쟁이 있습니다. 가격이나 조건으로 차별화가 필요합니다." },
    { min: 0, key: "crowded", label: "포화", note: "판매중인 리스팅에 비해 팔리는 수가 적습니다." },
  ];

  /** "3,600,000개 이상", "1.2K", "450" 같은 입력을 숫자로. 못 읽으면 null */
  function parseCount(v) {
    if (v === null || v === undefined) return null;
    let s = String(v).trim().toLowerCase().replace(/,/g, "").replace(/개|이상|results?|\+|\s/g, "");
    if (!s) return null;
    let mult = 1;
    if (s.endsWith("k")) { mult = 1e3; s = s.slice(0, -1); }
    else if (s.endsWith("m")) { mult = 1e6; s = s.slice(0, -1); }
    else if (s.endsWith("만")) { mult = 1e4; s = s.slice(0, -1); }
    if (!/^\d+(\.\d+)?$/.test(s)) return null;
    return Math.round(parseFloat(s) * mult);
  }

  /** 판매완료 수, 판매중 수 → 기회 정보. 입력이 부족하면 status로 이유를 알려준다 */
  function score(sold, active) {
    const s = parseCount(sold), a = parseCount(active);
    if (s === null || a === null) return { status: "missing", sold: s, active: a };
    if (a === 0) {
      return s > 0
        ? { status: "ok", sold: s, active: a, ratio: null, band: BANDS[0], note: "판매중인 리스팅이 없는데 최근 팔린 기록이 있습니다." }
        : { status: "empty", sold: s, active: a };
    }
    const ratio = s / a;
    const band = BANDS.find((b) => ratio >= b.min);
    return { status: "ok", sold: s, active: a, ratio: Math.round(ratio * 1000) / 1000, band };
  }

  /** 키워드로 eBay/네이버 검색 주소 만들기 */
  function links(keyword) {
    const q = encodeURIComponent(keyword.trim()).replace(/%20/g, "+");
    return {
      sold: `https://www.ebay.com/sch/i.html?_nkw=${q}&LH_Sold=1&LH_Complete=1`,
      active: `https://www.ebay.com/sch/i.html?_nkw=${q}`,
      completed: `https://www.ebay.com/sch/i.html?_nkw=${q}&LH_Complete=1`,
      naver: `https://search.shopping.naver.com/search/all?query=${q}`,
    };
  }

  const api = { BANDS, parseCount, score, links };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Opportunity = api;
})(typeof window !== "undefined" ? window : globalThis);
