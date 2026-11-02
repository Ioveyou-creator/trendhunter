// 키워드 기회 점수(docs/js/opportunity.js) 테스트. Node 내장 assert만 사용.
// 실행: node tests/js/opportunity.test.js  (tests/test_js.py 가 파이썬 테스트와 함께 실행)
const assert = require("assert");
const path = require("path");
const O = require(path.join(__dirname, "..", "..", "docs", "js", "opportunity.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

test("eBay 앱의 결과 수 표기를 숫자로 읽는다", () => {
  assert.strictEqual(O.parseCount("3,600,000개 이상"), 3600000);
  assert.strictEqual(O.parseCount("1.2K"), 1200);
  assert.strictEqual(O.parseCount("2만"), 20000);
  assert.strictEqual(O.parseCount(" 450 "), 450);
  assert.strictEqual(O.parseCount("1,234 results"), 1234);
  assert.strictEqual(O.parseCount(""), null);
  assert.strictEqual(O.parseCount("abc"), null);
});

test("비율에 따라 등급이 나뉜다", () => {
  assert.strictEqual(O.score(120, 100).band.key, "hot");      // 1.2
  assert.strictEqual(O.score(60, 100).band.key, "good");      // 0.6
  assert.strictEqual(O.score(50, 100).band.key, "good");      // 경계 0.5는 위 등급
  assert.strictEqual(O.score(30, 100).band.key, "fair");      // 0.3
  assert.strictEqual(O.score(5, 100).band.key, "crowded");    // 0.05
  assert.strictEqual(O.score(1, 3).ratio, 0.333);
});

test("입력이 비거나 0이면 이유를 알려준다", () => {
  assert.strictEqual(O.score("", 100).status, "missing");
  assert.strictEqual(O.score(0, 0).status, "empty");
  const noActive = O.score(5, 0);
  assert.strictEqual(noActive.status, "ok");
  assert.strictEqual(noActive.band.key, "hot");
  assert.strictEqual(noActive.ratio, null);
});

test("검색 링크에 필터가 들어간다", () => {
  const l = O.links("pokemon delta reign");
  assert.ok(l.sold.includes("_nkw=pokemon+delta+reign") && l.sold.includes("LH_Sold=1"));
  assert.ok(!l.active.includes("LH_"));
  assert.ok(l.completed.includes("LH_Complete=1") && !l.completed.includes("LH_Sold"));
  assert.ok(l.naver.includes("query=pokemon+delta+reign"));
  assert.ok(O.links("a&b").active.includes("a%26b"));  // 특수문자 인코딩
});

console.log(`opportunity.js: ${passed}개 테스트 통과`);
