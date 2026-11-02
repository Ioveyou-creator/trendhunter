/* 키워드 기회 점수 화면. 계산은 opportunity.js, 여기서는 입력·저장·그리기만 한다. */
(function () {
  "use strict";
  const O = window.Opportunity;
  const $ = (id) => document.getElementById(id);
  const KEY = "trendhunter.opportunity.v1";

  // 이 브라우저에만 저장하는 편의 기능. 저장이 막힌 환경에서도 화면은 동작해야 한다.
  function load() {
    try { const v = JSON.parse(localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v : []; }
    catch { return []; }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(rows)); } catch { /* 저장 못 해도 계속 */ }
  }

  let rows = load();

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
  const fmt = (n) => (n == null ? "-" : n.toLocaleString("ko-KR"));
  const pctText = (r) => (r == null ? "-" : Math.round(r * 100) + "%");

  function addKeyword(kw) {
    kw = kw.trim().replace(/\s+/g, " ");
    if (!kw) return;
    if (rows.some((r) => r.kw.toLowerCase() === kw.toLowerCase())) { render(); focusRow(kw); return; }
    rows.unshift({ kw, sold: "", active: "", sourcing: false });
    save(); render(); focusRow(kw);
  }

  function focusRow(kw) {
    const li = [...document.querySelectorAll(".kw")].find((x) => x.dataset.kw.toLowerCase() === kw.toLowerCase());
    if (li) { li.scrollIntoView({ block: "center" }); const i = li.querySelector("input[type=text]"); if (i) i.focus({ preventScroll: true }); }
  }

  function verdictNode(r) {
    const s = O.score(r.sold, r.active);
    if (s.status === "missing") return el("div", { class: "verdict", text: "판매완료 수와 판매중 수를 모두 적으면 결과가 나옵니다." });
    if (s.status === "empty") return el("div", { class: "verdict", text: "둘 다 0입니다. 검색어를 바꿔 보세요." });
    const ratioText = s.ratio == null ? "판매중 0개" : `판매완료 ÷ 판매중 = ${pctText(s.ratio)}`;
    return el("div", { class: "verdict band-" + s.band.key },
      el("b", { text: s.band.label }), " ",
      el("span", { class: "ratio", text: `(${ratioText})` }),
      el("div", { text: s.note || s.band.note }),
      el("div", { class: "section-note", style: "margin:6px 0 0",
        text: r.sourcing ? "국내 소싱 확인됨: 재고 없이 판매 가능" : "국내 소싱 확인 전: 팔린 뒤 바로 구할 수 있는지 네이버쇼핑에서 확인하세요" }));
  }

  function rowNode(r, i) {
    const l = O.links(r.kw);
    const ext = { target: "_blank", rel: "noopener noreferrer" };
    const soldIn = el("input", { type: "text", inputmode: "numeric", id: `sold-${i}`, value: r.sold, placeholder: "예: 1,240" });
    const activeIn = el("input", { type: "text", inputmode: "numeric", id: `active-${i}`, value: r.active, placeholder: "예: 3,600" });
    const src = el("input", { type: "checkbox", id: `src-${i}` });
    src.checked = !!r.sourcing;
    const verdictBox = el("div", {}, verdictNode(r));

    const update = () => {
      r.sold = soldIn.value; r.active = activeIn.value; r.sourcing = src.checked;
      save();
      verdictBox.replaceChildren(verdictNode(r));
      renderRank();
    };
    soldIn.addEventListener("input", update);
    activeIn.addEventListener("input", update);
    src.addEventListener("change", update);

    const remove = el("button", { type: "button", class: "kw-remove", text: "삭제", "aria-label": `${r.kw} 삭제` });
    remove.addEventListener("click", () => { rows = rows.filter((x) => x !== r); save(); render(); });

    return el("li", { class: "kw", "data-kw": r.kw },
      el("div", { class: "kw-head" }, el("h3", { class: "kw-name", text: r.kw }), remove),
      el("div", { class: "kw-links" },
        el("a", { href: l.sold, ...ext, text: "판매완료 결과 보기" }),
        el("a", { href: l.active, ...ext, text: "판매중 결과 보기" }),
        el("a", { href: l.naver, ...ext, text: "네이버쇼핑" }),
        el("a", { href: l.completed, ...ext, text: "완료 리스팅 (답안지용)" }),
        el("a", { href: "title.html?q=" + encodeURIComponent(r.kw), text: "제목 만들기" })),
      el("div", { class: "kw-inputs" },
        el("div", {}, el("label", { for: `sold-${i}`, text: "판매완료 수 (Sold items 결과)" }), soldIn),
        el("div", {}, el("label", { for: `active-${i}`, text: "판매중 수 (필터 없이 결과)" }), activeIn)),
      el("label", { class: "sourcing", for: `src-${i}` }, src, "국내에서 바로 구할 수 있음 (재고 없이 판매 가능)"),
      verdictBox);
  }

  function renderRank() {
    const scored = rows.map((r) => ({ r, s: O.score(r.sold, r.active) })).filter((x) => x.s.status === "ok");
    $("rank-sec").hidden = scored.length < 2;
    if (scored.length < 2) return;
    scored.sort((a, b) => (b.s.ratio ?? Infinity) - (a.s.ratio ?? Infinity));
    const t = $("rank-table");
    t.replaceChildren(
      el("thead", {}, el("tr", {}, el("th", { text: "키워드" }), el("th", { text: "판매완료" }), el("th", { text: "판매중" }),
        el("th", { text: "비율" }), el("th", { text: "판단" }), el("th", { text: "국내 소싱" }))),
      el("tbody", {}, ...scored.map(({ r, s }) => el("tr", {},
        el("td", { text: r.kw }), el("td", { class: "num", text: fmt(s.sold) }), el("td", { class: "num", text: fmt(s.active) }),
        el("td", { class: "num", text: s.ratio == null ? "-" : pctText(s.ratio) }),
        el("td", { class: "band-" + s.band.key }, el("b", { text: s.band.label })),
        el("td", { text: r.sourcing ? "확인됨" : "확인 전" })))));
  }

  function render() {
    $("kw-list").replaceChildren(...rows.map(rowNode));
    $("empty-note").hidden = rows.length > 0;
    renderRank();
  }

  $("add-form").addEventListener("submit", (e) => {
    e.preventDefault();
    addKeyword($("kw-input").value);
    $("kw-input").value = "";
  });

  // 대시보드에서 ?q=키워드 로 넘어온 경우 바로 추가
  const q = new URLSearchParams(location.search).get("q");
  render();
  if (q) addKeyword(q);
})();
