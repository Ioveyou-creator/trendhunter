/* 대시보드: data/latest.json + data/history/*.json 을 읽어 그린다.
 * 화면 구성
 *  - 새로 뜬 후보: 이벤트가 아닌 후보 (상품 신호 기반). 위에 "지금 준비할 이벤트" 한 줄.
 *  - 다가오는 이벤트: 이벤트 후보를 날짜 순으로.
 *  - 기타 급상승: 후보에서 뺀 검색어 + 어제 있다가 빠진 후보.
 * 행을 누르면 근거와 다음 단계(판매완료 확인 → 기회 점수 → 제목 만들기)가 열린다. */
(function () {
  "use strict";
  const SP = window.Sparkline;
  const $ = (id) => document.getElementById(id);
  const SOURCE_NAME = { google_trends: "Google Trends", reddit: "Reddit", events: "이벤트", news: "뉴스" };
  const FILTER_KEY = "trendhunter.filter";
  const TAB_KEY = "trendhunter.tab";
  const SPARK_DAYS = 14;

  let DATA = null;
  let SPARK = { dates: [], snaps: {} };
  const state = { category: read(FILTER_KEY) || "all", tab: read(TAB_KEY) || "trends" };

  function read(k) { try { return localStorage.getItem(k); } catch { return null; } }
  function store(k, v) { try { localStorage.setItem(k, v); } catch { /* 저장 못 해도 동작 */ } }

  function safeUrl(u) {
    if (!u) return null;
    try { const url = new URL(u, location.href); return /^https?:$/.test(url.protocol) ? url.href : null; }
    catch { return null; }
  }

  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k === "href") { const s = safeUrl(v); if (s) n.setAttribute("href", s); }
      else n.setAttribute(k, v);
    }
    for (const c of children) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return n;
  }
  const ext = (href, text, cls) => el("a", { href, text, class: cls, target: "_blank", rel: "noopener noreferrer" });
  const md = (d) => (d || "").slice(5).replace("-", "/");

  /* ---------- 불러오기 ---------- */
  async function load() {
    try {
      const res = await fetch("data/latest.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
    } catch (e) {
      $("status-line").textContent = "데이터를 불러오지 못했습니다.";
      document.body.classList.remove("loading");
      $("notice").replaceChildren(el("div", { class: "notice", role: "alert" },
        "data/latest.json을 읽지 못했습니다. 파일을 직접 열었다면 ",
        el("code", { text: "python -m http.server -d docs" }), " 로 띄운 뒤 접속하세요. (" + e.message + ")"));
      return;
    }
    renderAll();
    loadHistory().then(renderAll); // 추이 그래프는 뒤따라 채운다
  }

  async function loadHistory() {
    try {
      const idx = await (await fetch("data/history/index.json", { cache: "no-store" })).json();
      const today = DATA.date || "";
      const dates = (idx.dates || []).filter((d) => d <= today).sort().slice(-SPARK_DAYS);
      const snaps = {};
      await Promise.all(dates.map(async (d) => {
        try {
          const r = await fetch(`data/history/${d}.json`, { cache: "no-store" });
          if (!r.ok) return;
          const j = await r.json();
          const m = {};
          for (const c of j.candidates || []) m[c.id] = c.score;
          snaps[d] = m;
        } catch { /* 하루 빠져도 선만 끊긴다 */ }
      }));
      SPARK = { dates, snaps };
    } catch { /* 기록이 없으면 그래프 없이 */ }
  }

  /* ---------- 머리 ---------- */
  function renderHeader() {
    const d = (DATA.date || DATA.generated_at || "").slice(0, 10);
    if (d) {
      const [y, m, day] = d.split("-");
      const pm = $("postmark");
      pm.querySelector(".pm-year").textContent = y;
      pm.querySelector(".pm-day").textContent = `${m}.${day}`;
      pm.setAttribute("aria-label", `기준 날짜 ${y}년 ${+m}월 ${+day}일`);
    }
    const line = $("status-line");
    line.replaceChildren();
    for (const [key, s] of Object.entries(DATA.sources || {})) {
      line.append(el("span", { class: "src", title: s.error || "" },
        el("i", { class: "dot" + (s.ok ? "" : " fail"), "aria-hidden": "true" }),
        `${SOURCE_NAME[key] || key} ${s.ok ? s.count : "실패"}`));
    }
    const h = DATA.history || {};
    if (h.previous_date) line.append(el("span", {}, md(h.previous_date) + " 대비 ", el("strong", { text: "새로 등장 " + h.new_count + "개" })));
  }

  /* ---------- 분류 ---------- */
  const isEvent = (c) => !!c.event;
  function groups() {
    const cands = DATA.candidates || [];
    const trends = cands.filter((c) => !isEvent(c));
    const events = cands.filter(isEvent).sort((a, b) => a.event.days_left - b.event.days_left || b.score - a.score);
    return { trends, events, other: (DATA.other_trends || []).length + (DATA.dropped || []).length };
  }

  /* ---------- 행 ---------- */
  function moveBadge(t) {
    if (!t) return null;
    if (t.status === "new") return el("span", { class: "badge-new", text: "NEW" });
    if (t.status === "up") return el("span", { class: "mv-up", text: "▲" + t.rank_change, title: "어제 " + t.prev_rank + "위" });
    if (t.status === "down") return el("span", { class: "mv-down", text: "▼" + (-t.rank_change), title: "어제 " + t.prev_rank + "위" });
    return null;
  }

  function sparkFor(c) {
    if (!SPARK.dates.length) return null;
    const values = SP.series(c.id, SPARK.dates, SPARK.snaps);
    // 하루만 있었던 후보(NEW)는 그릴 선이 없어 생략
    if (values.filter((v) => v != null).length < 2) return null;
    return el("span", { class: "spark" }, SP.svg(values, SPARK.dates));
  }

  function detailBody(c) {
    const L = c.links || {};
    const q = encodeURIComponent(c.query || c.title);
    return el("div", { class: "row-body" },
      el("p", { class: "query-line" }, "검색어 ", el("b", { text: c.query })),
      el("div", { class: "actions" },
        ext(L.ebay_sold, "① eBay 판매완료 확인", "primary"),
        el("a", { href: "opportunity.html?q=" + q, text: "② 기회 점수" }),
        el("a", { href: "title.html?q=" + q, text: "③ 제목 만들기" }),
        ext(L.ebay_active, "eBay 판매중"),
        ext(L.naver, "네이버쇼핑")),
      el("ul", {}, ...(c.reasons || []).map((r) => el("li", { text: r }))),
      el("ul", { class: "ev-list" }, ...(c.evidence || []).map((e) => el("li", {},
        el("span", { class: "src-name", text: SOURCE_NAME[e.source] || e.source }),
        safeUrl(e.url) ? ext(e.url, e.text) : (e.text || "")))));
  }

  function row(c, lead) {
    const t = c.trend || {};
    const meta = el("div", { class: "r-meta" },
      lead || null,
      el("span", { text: c.category_label || c.category }),
      sparkFor(c),
      t.streak > 1 ? el("span", { text: `${t.streak}일째` }) : null,
      el("span", { text: (c.sources || []).map((s) => SOURCE_NAME[s] || s).join("·") }));
    const summary = el("summary", {},
      el("h2", { class: "r-title" }, moveBadge(t), c.title),
      meta,
      el("div", { class: "r-score", "aria-label": `점수 ${c.score}점` }, el("b", { text: c.score }), el("span", { text: "점수" })));
    const d = el("details", { class: "row-d" }, summary);
    // 펼칠 때 만든다 (첫 화면을 가볍게)
    d.addEventListener("toggle", () => { if (d.open && d.children.length === 1) d.append(detailBody(c)); });
    return el("li", { class: "cand-row" + (c.event && c.event.status === "prepare_now" ? " ev-now" : "") }, d);
  }

  /* ---------- 탭별 ---------- */
  function renderFilters(trends) {
    const box = $("filters");
    const counts = new Map();
    for (const c of trends) {
      const p = counts.get(c.category) || { label: c.category_label || c.category, n: 0 };
      p.n++; counts.set(c.category, p);
    }
    if (state.category !== "all" && !counts.has(state.category)) state.category = "all";
    const mk = (key, label, n) => {
      const b = el("button", { type: "button", "aria-pressed": String(state.category === key) }, `${label} ${n}`);
      b.addEventListener("click", () => { state.category = key; store(FILTER_KEY, key); renderTrends(); });
      return b;
    };
    box.replaceChildren(mk("all", "전체", trends.length), ...[...counts].map(([k, v]) => mk(k, v.label, v.n)));
    box.hidden = counts.size < 2;
  }

  function renderNowStrip(events) {
    const now = events.filter((c) => c.event.status === "prepare_now");
    const box = $("now-strip");
    box.hidden = !now.length;
    if (!now.length) return;
    const go = el("button", { type: "button", text: "이벤트 보기" });
    go.addEventListener("click", () => selectTab("events", true));
    box.replaceChildren(el("b", { text: `지금 준비 ${now.length}` }),
      el("span", { text: now.slice(0, 3).map((c) => `${c.title} D-${c.event.days_left}`).join(" · ") + (now.length > 3 ? " …" : "") }), go);
  }

  function renderTrends() {
    const { trends, events } = groups();
    renderFilters(trends);
    renderNowStrip(events);
    const shown = trends.filter((c) => state.category === "all" || c.category === state.category);
    const ol = $("rows-trends");
    ol.replaceChildren(...(shown.length ? shown.map((c) => row(c)) : [el("li", { class: "empty", text: "오늘은 상품 신호가 있는 새 후보가 없습니다. 이벤트 탭을 확인하세요." })]));
  }

  function prepText(e) {
    if (e.status === "prepare_now") return "지금 준비";
    if (e.status === "too_late") return "배송 시간 부족";
    return md(e.prep_by) + "부터 준비";
  }

  function renderEvents() {
    const { events } = groups();
    const ol = $("rows-events");
    ol.replaceChildren(...(events.length ? events.map((c) => row(c,
      el("span", { class: "ev-when", text: `D-${c.event.days_left} ${md(c.event.date)}` }))) : [el("li", { class: "empty", text: "앞으로 60일 안에 등록된 이벤트가 없습니다." })]));
    // 이벤트 행의 상태 글자 덧붙이기
    events.forEach((c, i) => {
      const meta = ol.children[i] && ol.children[i].querySelector(".r-meta");
      if (meta) meta.append(el("span", { class: "ev-state", text: prepText(c.event) }));
    });

    // 넓은 화면 옆 칸: 캘린더 전체 (후보로 안 잡힌 이벤트 포함)
    const aside = $("aside-events");
    const all = DATA.events || [];
    aside.replaceChildren(...(all.length ? all.slice(0, 8).map((e) => el("li", { class: e.status === "prepare_now" ? "ev-now" : "" },
      el("span", { class: "ev-when", text: `D-${e.days_left}` }),
      el("span", {}, e.name, el("br"), el("span", { class: "ev-state", text: `${md(e.date)} · ${prepText(e)}` })))) : [el("li", { text: "등록된 이벤트 없음" })]));
  }

  function renderOther() {
    const ol = $("rows-other");
    const items = [];
    for (const o of DATA.other_trends || []) {
      items.push(el("li", {}, el("div", { class: "row-plain" },
        ext((o.links || {}).ebay_sold, o.keyword, "r-title"),
        el("span", { class: "ev-state", text: `미국 검색 ${o.traffic_label || ""}` }))));
    }
    for (const d of (DATA.dropped || []).slice(0, 10)) {
      items.push(el("li", {}, el("div", { class: "row-plain" },
        el("span", { class: "r-title", text: d.title }),
        el("span", { class: "ev-state", text: `어제 ${d.rank}위 → 빠짐` }))));
    }
    ol.replaceChildren(...(items.length ? items : [el("li", { class: "empty", text: "없음" })]));
  }

  /* ---------- 탭 ---------- */
  const TABS = ["trends", "events", "other"];
  function selectTab(name, focus) {
    if (!TABS.includes(name)) name = "trends";
    state.tab = name; store(TAB_KEY, name);
    for (const t of TABS) {
      const b = $("tab-" + t), p = $("panel-" + t), on = t === name;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
      p.hidden = !on;
      if (on && focus) b.focus();
    }
  }
  TABS.forEach((t, i) => {
    const b = $("tab-" + t);
    b.addEventListener("click", () => selectTab(t));
    b.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (d) { e.preventDefault(); selectTab(TABS[(i + d + TABS.length) % TABS.length], true); }
    });
  });

  function renderAll() {
    renderHeader();
    document.body.classList.remove("loading");
    const g = groups();
    $("cnt-trends").textContent = g.trends.length;
    $("cnt-events").textContent = g.events.length;
    $("cnt-other").textContent = g.other;
    // 펼쳐 둔 행은 다시 그려도 유지
    const open = new Set([...document.querySelectorAll(".row-d[open] .r-title")].map((n) => n.textContent));
    renderTrends(); renderEvents(); renderOther();
    document.querySelectorAll(".row-d").forEach((d) => {
      if (open.has(d.querySelector(".r-title").textContent)) { d.open = true; }
    });
    selectTab(state.tab);
  }

  load();
})();
