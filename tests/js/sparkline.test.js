// 점수 추이(docs/js/sparkline.js) 테스트. Node 내장 assert만 사용.
const assert = require("assert");
const path = require("path");
const SP = require(path.join(__dirname, "..", "..", "docs", "js", "sparkline.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

const dates = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"];
const snaps = {
  "2026-10-30": { a: 40 },
  "2026-10-31": { a: 50, b: 10 },
  // 11-01 기록 파일 없음
  "2026-11-02": { a: 70, b: 0 },
};

test("같은 id의 점수를 날짜순으로 모으고, 없는 날은 null", () => {
  assert.deepStrictEqual(SP.series("a", dates, snaps), [40, 50, null, 70]);
  assert.deepStrictEqual(SP.series("b", dates, snaps), [null, 10, null, 0]); // 0점도 값으로 본다
  assert.deepStrictEqual(SP.series("zz", dates, snaps), [null, null, null, null]);
});

test("연속 등장 일수는 오늘부터 거꾸로 센다", () => {
  assert.strictEqual(SP.streak([40, 50, null, 70]), 1);
  assert.strictEqual(SP.streak([40, 50, 60, 70]), 4);
  assert.strictEqual(SP.streak([40, null]), 0);
});

test("빈 날에서 선이 끊기고, 점수 축은 0~100 고정", () => {
  const g = SP.geometry([40, 50, null, 70], 64, 20, 3);
  assert.strictEqual(g.segs.length, 2);
  assert.strictEqual(g.segs[0].length, 2);
  assert.deepStrictEqual(g.last, [61, 7.2]); // y = 3 + (1-0.7)*14 = 7.2
  const hi = SP.geometry([100], 64, 20, 3), lo = SP.geometry([0], 64, 20, 3);
  assert.strictEqual(hi.last[1], 3);
  assert.strictEqual(lo.last[1], 17);
  assert.strictEqual(SP.geometry([150], 64, 20, 3).last[1], 3); // 범위 밖은 자른다
  assert.strictEqual(SP.geometry([40, null], 64, 20, 3).last, null); // 오늘 없으면 강조점 없음
});

test("설명 문장 (툴팁, 스크린리더)", () => {
  assert.strictEqual(SP.describe([40, 50, null, 70], dates), "최근 4일 중 3일 등장, 10/30 40점 → 11/02 70점");
  assert.strictEqual(SP.describe([null, null], dates.slice(0, 2)), "기록 없음");
});

console.log(`sparkline: ${passed}개 통과`);
