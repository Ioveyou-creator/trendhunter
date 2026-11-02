/* 리스팅 제목 빌더 화면. 계산은 title-builder.js / listing-parser.js */
(function () {
  "use strict";
  const T = window.TitleBuilder, P = window.ListingParser;
  const $ = (id) => document.getElementById(id);
  const KEY = "trendhunter.title.v1";

  const HINTS = {
    brand: "예: Pokemon, NOVA, Nintendo",
    name: "예: Delta Reign Booster Box",
    number: "예: ME06, 177/132, Ver 2",
    feature: "예: with Photocard, 36 Packs",
    condition: "예: Sealed, NM, Brand New",
    region: "예: Korean Ver, English, Japanese",
  };

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

  // 입력 칸 만들기 (추가 키워드는 아래 별도 칸)
  const inputs = {};
  for (const p of T.PARTS.filter((p) => p.key !== "extra")) {
    const id = "f-" + p.key;
    const input = el("input", { type: "text", id, autocomplete: "off", placeholder: HINTS[p.key] });
    inputs[p.key] = input;
    $("fields").append(el("div", { class: "fld" }, el("label", { class: "field", for: id, text: p.label + (p.keep ? " (필수)" : "") }), input));
  }

  function readParts() {
    const parts = {};
    for (const k in inputs) parts[k] = inputs[k].value;
    parts.extra = $("extra").value.split(",").map((s) => s.trim()).filter(Boolean);
    return parts;
  }

  function saveDraft() {
    try { localStorage.setItem(KEY, JSON.stringify(readParts())); } catch { /* 저장 못 해도 계속 */ }
  }
  function loadDraft() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; }
  }

  let lastResult = null;   // 답안지 분석 결과 (빠진 키워드 제안용)
  let soldTitles = [];     // 팔린 리스팅 제목 (대소문자 참고용)
  let current = { title: "" };

  function renderChecks(title) {
    const ul = $("checks");
    ul.replaceChildren(...T.checkTitle(title).map((c) =>
      el("li", { class: "chk chk-" + c.level }, el("span", { class: "chk-mark", "aria-hidden": "true", text: c.level === "ok" ? "✓" : c.level === "error" ? "✕" : "!" }), c.msg)));
  }

  function renderChips() {
    const box = $("chips");
    if (!lastResult) { box.replaceChildren(el("p", { class: "section-note", text: "답안지를 넣으면 여기에 제안이 나옵니다." })); return; }
    const sug = T.suggestKeywords(lastResult, current.title, P.tokens);
    if (!sug.length) { box.replaceChildren(el("p", { class: "section-note", text: "팔린 리스팅에 자주 나온 단어는 이미 제목에 모두 들어 있습니다." })); return; }
    box.replaceChildren(...sug.map((s) => {
      const word = T.originalCase(s.term, soldTitles);
      const b = el("button", { type: "button", class: "chip", title: `팔린 리스팅 ${s.soldWith}개에 나옴, 판매율 차이 +${Math.round(s.gap * 100)}%p. 누르면 "핵심 특징" 칸에 들어갑니다` },
        "+ " + word, el("span", { class: "chip-meta", text: ` 팔림 ${s.soldWith}` }));
      b.addEventListener("click", () => {
        // 답안지 근거가 있는 단어라 제목 앞쪽(핵심 특징)에 넣는다. 맨 끝은 80자를 넘으면 먼저 잘리는 자리
        const cur = inputs.feature.value.trim();
        inputs.feature.value = cur ? cur + " " + word : word;
        update();
      });
      return b;
    }));
  }

  function update() {
    const r = T.buildTitle(readParts());
    current = r;
    const out = $("title-out");
    out.textContent = r.title || "칸을 채우면 여기에 제목이 만들어집니다.";
    out.classList.toggle("empty", !r.title);
    const fill = $("len-fill");
    fill.style.width = Math.min(100, (r.length / T.MAX_LEN) * 100) + "%";
    fill.classList.toggle("over", r.length > T.MAX_LEN);

    const d = $("dropped");
    const notes = [];
    if (r.dropped.length) notes.push("80자를 넘어서 뺀 부분: " + r.dropped.map((x) => `${x.label} "${x.text}"`).join(", "));
    if (r.truncated) notes.push("브랜드와 상품명만으로 80자를 넘어 끝을 잘랐습니다. 상품명을 줄여 주세요.");
    d.textContent = notes.join(" / ");
    d.hidden = !notes.length;

    renderChecks(r.title);
    renderChips();
    saveDraft();
  }

  function runSheet(text) {
    const parsed = P.parse(text, "");
    const msg = $("sheet-msg");
    if (!parsed.listings.length) { lastResult = null; msg.textContent = "리스팅을 찾지 못했습니다. '판매됨/종료됨 날짜' 줄이 포함됐는지 확인하세요."; renderChips(); return; }
    lastResult = P.analyze(parsed.listings);
    soldTitles = parsed.listings.filter((l) => l.status === "sold").map((l) => l.title);
    const c = lastResult.counts;
    msg.textContent = `리스팅 ${c.total}개 (팔림 ${c.sold}, 안 팔림 ${c.unsold})를 읽었습니다.` + (lastResult.small_sample ? " 표본이 작아 제안이 우연일 수 있습니다." : "");
    renderChips();
  }

  for (const k in inputs) inputs[k].addEventListener("input", update);
  $("extra").addEventListener("input", update);
  $("sheet-run").addEventListener("click", () => runSheet($("sheet").value));
  $("sheet-sample").addEventListener("click", async () => {
    try {
      const res = await fetch("samples/nova_orbit_synthetic.txt", { cache: "no-store" });
      $("sheet").value = await res.text();
      inputs.brand.value = inputs.brand.value || "NOVA";
      inputs.name.value = inputs.name.value || "Orbit 2nd Mini Album";
      inputs.condition.value = inputs.condition.value || "Sealed";
      inputs.region.value = inputs.region.value || "Korean Ver";
      update();
      runSheet($("sheet").value);
    } catch (e) {
      $("sheet-msg").textContent = "예시를 불러오지 못했습니다. 붙여넣기는 그대로 됩니다.";
    }
  });
  $("copy").addEventListener("click", async () => {
    if (!current.title) return;
    try { await navigator.clipboard.writeText(current.title); $("copy-msg").textContent = "복사했습니다."; }
    catch { $("copy-msg").textContent = "복사하지 못했습니다. 제목을 길게 눌러 직접 복사하세요."; }
  });

  // 초기값: ?q=검색어 가 있으면 상품명에, 없으면 이 브라우저에 저장된 초안
  const q = new URLSearchParams(location.search).get("q");
  const draft = loadDraft();
  if (q) inputs.name.value = q;
  else if (draft) {
    for (const k in inputs) inputs[k].value = draft[k] || "";
    $("extra").value = (draft.extra || []).join(", ");
  }
  update();
})();
