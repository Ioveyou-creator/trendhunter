/* 후보별 점수 추이 (스파크라인)
 * - 기록 파일(data/history/날짜.json)에서 같은 id의 점수를 날짜순으로 모은다.
 * - 후보에 없던 날은 null (선을 끊는다). 점수 축은 0~100 고정이라 행끼리 높이를 비교할 수 있다.
 * - 선 하나는 흐린 색, 오늘 점은 강조색. 범례 없음(선이 하나뿐), 값은 title/aria-label로.
 * 브라우저와 Node 테스트 양쪽에서 쓴다. */
(function (root) {
  "use strict";

  // dates: 오래된 날 → 오늘 순서, snaps: { 날짜: {id: score} }
  function series(id, dates, snaps) {
    return dates.map((d) => {
      const m = snaps[d];
      return m && Object.prototype.hasOwnProperty.call(m, id) ? m[id] : null;
    });
  }

  // 연속으로 등장한 날 수 (오늘부터 거꾸로)
  function streak(values) {
    let n = 0;
    for (let i = values.length - 1; i >= 0 && values[i] != null; i--) n++;
    return n;
  }

  // 점수 배열 → 선분 목록(끊긴 구간마다 하나) + 마지막 점
  function geometry(values, w, h, pad) {
    const n = values.length;
    const x = (i) => (n <= 1 ? w / 2 : pad + (i * (w - 2 * pad)) / (n - 1));
    const y = (v) => pad + (1 - Math.max(0, Math.min(100, v)) / 100) * (h - 2 * pad);
    const segs = [];
    let cur = [];
    values.forEach((v, i) => {
      if (v == null) { if (cur.length) segs.push(cur); cur = []; return; }
      cur.push([+x(i).toFixed(1), +y(v).toFixed(1)]);
    });
    if (cur.length) segs.push(cur);
    const lastIdx = values.length - 1;
    const last = lastIdx >= 0 && values[lastIdx] != null ? [+x(lastIdx).toFixed(1), +y(values[lastIdx]).toFixed(1)] : null;
    return { segs, last };
  }

  function describe(values, dates) {
    const seen = values.map((v, i) => (v == null ? null : { v, d: dates[i] })).filter(Boolean);
    if (!seen.length) return "기록 없음";
    const first = seen[0], lastV = seen[seen.length - 1];
    const md = (d) => d.slice(5).replace("-", "/");
    return `최근 ${values.length}일 중 ${seen.length}일 등장, ${md(first.d)} ${first.v}점 → ${md(lastV.d)} ${lastV.v}점`;
  }

  // 브라우저 전용: SVG 요소 만들기
  function svg(values, dates, opts) {
    const o = Object.assign({ w: 64, h: 20, pad: 3 }, opts || {});
    const NS = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("width", o.w);
    s.setAttribute("height", o.h);
    s.setAttribute("viewBox", `0 0 ${o.w} ${o.h}`);
    s.setAttribute("role", "img");
    const label = describe(values, dates);
    s.setAttribute("aria-label", "점수 추이: " + label);
    const t = document.createElementNS(NS, "title");
    t.textContent = label;
    s.append(t);
    // 마우스 판정 영역은 선보다 크게 (투명 사각형)
    const hit = document.createElementNS(NS, "rect");
    hit.setAttribute("width", o.w); hit.setAttribute("height", o.h); hit.setAttribute("fill", "transparent");
    s.append(hit);
    const g = geometry(values, o.w, o.h, o.pad);
    for (const seg of g.segs) {
      if (seg.length === 1) { // 하루만 등장한 날은 작은 점으로
        const d = document.createElementNS(NS, "circle");
        d.setAttribute("cx", seg[0][0]); d.setAttribute("cy", seg[0][1]); d.setAttribute("r", "1.5");
        d.setAttribute("fill", "var(--muted)"); d.setAttribute("fill-opacity", ".7");
        s.append(d);
        continue;
      }
      const p = document.createElementNS(NS, "polyline");
      p.setAttribute("points", seg.map((pt) => pt.join(",")).join(" "));
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "var(--muted)");
      p.setAttribute("stroke-opacity", ".55");
      p.setAttribute("stroke-width", "2");
      p.setAttribute("stroke-linejoin", "round");
      p.setAttribute("stroke-linecap", "round");
      s.append(p);
    }
    if (g.last) {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", g.last[0]); c.setAttribute("cy", g.last[1]); c.setAttribute("r", "3");
      c.setAttribute("fill", "var(--mail-blue)");
      c.setAttribute("stroke", "var(--sheet)"); c.setAttribute("stroke-width", "1.5");
      s.append(c);
    }
    return s;
  }

  const api = { series, streak, geometry, describe, svg };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Sparkline = api;
})(typeof window !== "undefined" ? window : globalThis);
