/* 답안지 분석기 화면. 계산은 listing-parser.js 가 하고, 여기서는 화면에 그리기만 한다. */
(function () {
  "use strict";
  const P = window.ListingParser;
  const $ = (id) => document.getElementById(id);
  let last = null; // 마지막 분석 결과 (복사용)

  // 외부 데이터(제목 등)는 항상 글자로만 넣는다
  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else n.setAttribute(k, v);
    }
    for (const c of children) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return n;
  }

  const pct = (v) => (v == null ? "-" : Math.round(v * 100) + "%");
  function money(v, cur) {
    if (v == null) return "-";
    if (cur === "KRW") return "₩" + Math.round(v).toLocaleString("ko-KR");
    return "$" + v.toFixed(2);
  }
  function gapCell(g) {
    const t = g == null ? "-" : (g > 0 ? "+" : "") + Math.round(g * 100) + "%p";
    return el("td", { class: "num " + (g > 0 ? "gap-pos" : g < 0 ? "gap-neg" : "") }, t);
  }
  function rateCell(side) {
    const w = side.sell_through == null ? 0 : Math.max(2, Math.round(side.sell_through * 60));
    return el("td", { class: "num" },
      el("span", { class: "bar" + (side.sell_through ? "" : " off"), style: `width:${w}px`, "aria-hidden": "true" }),
      `${pct(side.sell_through)} (${side.sold}/${side.n})`);
  }
  const isSmall = (f) => Math.min(f.with.n, f.without.n) < P.MIN_SUPPORT;

  function compareTable(table, rows, label) {
    table.textContent = "";
    table.append(el("thead", {}, el("tr", {},
      el("th", { text: label }), el("th", { text: "있을 때 판매율 (팔림/전체)" }),
      el("th", { text: "없을 때 판매율" }), el("th", { text: "차이" }))));
    const tb = el("tbody");
    if (!rows.length) tb.append(el("tr", {}, el("td", { colspan: "4", text: "비교할 수 있는 항목이 없습니다." })));
    for (const f of rows) {
      tb.append(el("tr", {},
        el("td", {}, f.feature, isSmall(f) ? el("span", { class: "tag small", text: "표본 작음" }) : null),
        rateCell(f.with), rateCell(f.without), gapCell(f.gap)));
    }
    table.append(tb);
  }

  function showError(msg) {
    $("errors").textContent = "";
    if (msg) $("errors").append(el("div", { class: "notice err", role: "alert", text: msg }));
  }

  function render(parsed, r) {
    const cur = r.currency;
    const c = r.counts;
    $("summary").textContent = "";
    $("summary").append("리스팅 ", el("b", { text: c.total + "개" }), " = 팔림 ", el("b", { text: c.sold + "개" }),
      " + 안 팔림 ", el("b", { text: c.unsold + "개" }), `, 전체 판매율 ${pct(c.sell_through)}`);

    const warn = $("warnings");
    warn.textContent = "";
    const w = (t) => warn.append(el("div", { class: "notice warn", text: t }));
    if (!c.sold || !c.unsold) w("팔린 리스팅과 안 팔린 리스팅이 둘 다 있어야 비교할 수 있습니다. Sold items 필터가 켜져 있지 않은지 확인하세요.");
    if (r.small_sample) w("표본이 작습니다 (팔림 또는 안 팔림이 5개 미만). 아래 차이는 우연일 수 있습니다.");
    if (r.mixed_currency) w("달러와 원화가 섞여 있어 가격 비교가 의미 없습니다. 한 화폐로 다시 모으세요.");
    if (r.missing_price) w(`가격이 보이지 않은 리스팅 ${r.missing_price}개는 가격 비교에서 빠졌습니다.`);
    if (parsed.unparsed.length) w(`인식하지 못한 줄이 ${parsed.unparsed.length}개 있습니다. 맨 아래에서 확인하세요.`);

    const pt = $("price-table");
    pt.textContent = "";
    pt.append(el("thead", {}, el("tr", {}, el("th", { text: "" }), el("th", { text: "팔림" }), el("th", { text: "안 팔림" }))));
    const ptb = el("tbody");
    ptb.append(el("tr", {}, el("td", { text: "가격 중앙값" }),
      el("td", { class: "num", text: money(r.price.median_price_sold, cur) }),
      el("td", { class: "num", text: money(r.price.median_price_unsold, cur) })));
    ptb.append(el("tr", {}, el("td", { text: "총액(가격+배송) 중앙값" }),
      el("td", { class: "num", text: money(r.price.median_total_sold, cur) }),
      el("td", { class: "num", text: money(r.price.median_total_unsold, cur) })));
    pt.append(ptb);

    compareTable($("feat-table"), r.features, "조건");
    $("kw-note").textContent = `제목에 ${P.MIN_SUPPORT}번 이상 나온 단어와 두 단어 묶음입니다. 차이가 큰 순서.`;
    compareTable($("kw-table"), r.keywords_top, "키워드");

    const lt = $("list-table");
    lt.textContent = "";
    lt.append(el("thead", {}, el("tr", {}, el("th", { text: "상태" }), el("th", { text: "가격" }),
      el("th", { text: "배송" }), el("th", { text: "형식" }), el("th", { text: "제목" }))));
    const ltb = el("tbody");
    for (const l of parsed.listings) {
      const fmt = [l.auction ? `경매(입찰 ${l.bids})` : null, l.offer_accepted ? "오퍼 수락" : l.best_offer ? "오퍼 가능" : null,
        l.location ? "출발지 " + l.location : null].filter(Boolean).join(", ");
      ltb.append(el("tr", {},
        el("td", { class: l.status === "sold" ? "st-sold" : "st-unsold", text: l.status === "sold" ? "팔림" : "안 팔림" }),
        el("td", { class: "num", text: money(l.price, l.currency || cur) }),
        el("td", { class: "num", text: l.shipping === 0 ? "무료" : money(l.shipping, l.currency || cur) }),
        el("td", { text: fmt || "-" }),
        el("td", { text: l.title })));
    }
    lt.append(ltb);

    $("unparsed-sec").hidden = !parsed.unparsed.length;
    const ul = $("unparsed");
    ul.textContent = "";
    for (const u of parsed.unparsed.slice(0, 50)) ul.append(el("li", { text: u }));

    $("results").hidden = false;
  }

  // 스킬(AI)에게 넘길 때 쓰는 텍스트
  function toText(parsed, r) {
    const product = $("product").value.trim() || "(상품명 미입력)";
    const cur = r.currency;
    const lines = [
      `# 답안지: ${product}`,
      `리스팅 ${r.counts.total}개 = 팔림 ${r.counts.sold} + 안 팔림 ${r.counts.unsold} (판매율 ${pct(r.counts.sell_through)})`,
      `가격 중앙값: 팔림 ${money(r.price.median_price_sold, cur)} / 안 팔림 ${money(r.price.median_price_unsold, cur)}`,
      r.small_sample ? "주의: 표본 작음" : "",
      "", "## 조건별 판매율 (있을 때 / 없을 때 / 차이)",
      ...r.features.map((f) => `- ${f.feature}: ${pct(f.with.sell_through)} (${f.with.n}) / ${pct(f.without.sell_through)} (${f.without.n}) / ${pct(f.gap)}`),
      "", "## 제목 키워드별 판매율",
      ...r.keywords_top.map((f) => `- ${f.feature}: ${pct(f.with.sell_through)} (${f.with.n}) / ${pct(f.without.sell_through)} (${f.without.n}) / ${pct(f.gap)}`),
      "", "## 리스팅 (상태, 가격, 배송, 제목)",
      ...parsed.listings.map((l) => `- ${l.status === "sold" ? "팔림" : "안 팔림"} | ${money(l.price, cur)} | ${l.shipping === 0 ? "무료" : money(l.shipping, cur)} | ${l.title}`),
    ];
    return lines.filter((x, i) => x !== "" || lines[i - 1] !== "").join("\n");
  }

  function run() {
    const text = $("raw").value;
    if (!text.trim()) { showError("분석할 내용이 없습니다. eBay 완료 리스팅을 붙여넣거나 예시를 불러오세요."); $("results").hidden = true; return; }
    const parsed = P.parse(text, $("raw").dataset.filename || "");
    if (!parsed.listings.length) {
      showError("리스팅을 하나도 찾지 못했습니다. '판매됨 날짜' / '종료됨 날짜'(영어 화면은 Sold / Ended) 줄이 포함되도록 복사했는지, CSV라면 title, status 열이 있는지 확인하세요.");
      $("results").hidden = true;
      return;
    }
    showError("");
    const r = P.analyze(parsed.listings);
    last = { parsed, r };
    render(parsed, r);
    $("results").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  async function loadSample(path, product) {
    try {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      $("raw").value = await res.text();
      $("raw").dataset.filename = path;
      $("product").value = product;
      run();
    } catch (e) {
      showError(location.protocol === "file:"
        ? "파일을 직접 열면 예시를 불러올 수 없습니다. python -m http.server -d docs 로 연 뒤 다시 시도하세요. (붙여넣기는 그대로 됩니다)"
        : "예시 파일을 불러오지 못했습니다 (" + e.message + ").");
    }
  }

  $("run").addEventListener("click", run);
  $("clear").addEventListener("click", () => {
    $("raw").value = ""; $("product").value = ""; delete $("raw").dataset.filename;
    $("results").hidden = true; showError("");
  });
  $("raw").addEventListener("input", () => { delete $("raw").dataset.filename; });
  $("file").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    $("raw").value = await f.text();
    $("raw").dataset.filename = f.name;
    run();
  });
  $("sample-real").addEventListener("click", () => loadSample("samples/pokemon_kr_2026-11-02.txt", "pokemon (넓은 검색, 형식 확인용)"));
  $("sample-synth").addEventListener("click", () => loadSample("samples/nova_orbit_synthetic.txt", "NOVA Orbit 앨범 (가상 데이터)"));
  $("copy").addEventListener("click", async () => {
    if (!last) return;
    try {
      await navigator.clipboard.writeText(toText(last.parsed, last.r));
      $("copy-msg").textContent = "복사했습니다. AI에게 붙여넣고 핵심 변수를 물어보세요.";
    } catch {
      $("copy-msg").textContent = "복사하지 못했습니다. 브라우저가 클립보드 접근을 막았습니다.";
    }
  });
})();
