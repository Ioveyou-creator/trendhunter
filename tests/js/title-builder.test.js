// 리스팅 제목 빌더(docs/js/title-builder.js) 테스트
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const T = require(path.join(__dirname, "..", "..", "docs", "js", "title-builder.js"));
const P = require(path.join(__dirname, "..", "..", "docs", "js", "listing-parser.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }
const codes = (title) => T.checkTitle(title).map((c) => c.code);

test("중요한 순서대로 조립하고 앞에 나온 단어는 반복하지 않는다", () => {
  const r = T.buildTitle({ brand: "NOVA", name: "Orbit 2nd Mini Album", feature: "with Photocard", condition: "Sealed", region: "Korean Ver", extra: ["Album", "POB"] });
  assert.strictEqual(r.title, "NOVA Orbit 2nd Mini Album with Photocard Sealed Korean Ver POB");
  assert.deepStrictEqual(r.dropped, []);
});

test("80자를 넘으면 뒤쪽(덜 중요한) 칸부터 뺀다", () => {
  const r = T.buildTitle({
    brand: "Pokemon", name: "Scarlet Violet Delta Reign Booster Box", number: "ME06 36 Packs",
    feature: "Factory Sealed English", condition: "Brand New", region: "US Version", extra: ["TCG Card Game", "Display"],
  });
  assert.ok(r.length <= 80, r.title);
  assert.ok(r.title.startsWith("Pokemon Scarlet Violet Delta Reign Booster Box"));
  assert.ok(r.dropped.length >= 1);
  assert.strictEqual(r.dropped[r.dropped.length - 1].key, "extra"); // 가장 덜 중요한 것부터
  assert.strictEqual(r.truncated, false);
});

test("브랜드+상품명만으로 80자를 넘으면 단어 단위로 자르고 알린다", () => {
  // 같은 단어를 반복하면 빌더가 중복을 지워 버리므로 서로 다른 단어 30개로 만든다
  const r = T.buildTitle({ brand: "Brand", name: Array.from({ length: 30 }, (_, i) => "word" + i).join(" ") });
  assert.ok(r.length <= 80);
  assert.ok(!r.title.endsWith(" "));
  assert.strictEqual(r.truncated, true);
});

test("제목 점검", () => {
  assert.ok(codes("x".repeat(81)).includes("too_long"));
  assert.ok(codes("Pokemon Card").includes("short"));
  assert.ok(codes("2008 POKEMON IGGLYBUFF GREAT ENCOUNTERS COMMON REVERSE HOLO CARD").includes("caps"));
  // NM, PSA, ETB 같은 짧은 약어는 대문자여도 괜찮다
  assert.ok(!codes("Pokemon Mega Venusaur ex 177/132 SIR Mega Evolution PSA 10 NM ETB Sealed").includes("caps"));
  assert.ok(codes("L@@K Rare Pokemon Card WOW!!! Charizard Holo Vintage 1999 Base Set Unlimited").includes("decoration"));
  assert.ok(codes("Pokemon Lugia Lugia Reverse Holo Fates Collide 78/124 Near Mint Card Single Rare").includes("repeat"));
  assert.ok(codes("Pokemon Delta Reign Booster Box Sealed English Free Shipping Fast From Korea").includes("shipping"));
  assert.ok(codes("Pokemon Gwynn 119/084 Pitch Black Special Illustration Rare Holo Trainer 🔥🔥").includes("emoji"));
  const clean = T.checkTitle("NOVA Orbit 2nd Mini Album with Photocard POB Sealed Korean Ver Official KR");
  assert.deepStrictEqual(clean.map((c) => c.level), ["ok"]);
});

test("답안지에서 팔린 리스팅에 자주 나온 빠진 단어를 제안한다", () => {
  const text = fs.readFileSync(path.join(__dirname, "..", "..", "skills", "ebay-seo-lens", "evals", "kpop-photocard-keyword", "files", "nova_orbit.txt"), "utf8");
  const parsed = P.parse(text, "nova.txt");
  const res = P.analyze(parsed.listings);
  const s = T.suggestKeywords(res, "NOVA Orbit 2nd Mini Album Sealed Korean Ver", P.tokens);
  const terms = s.map((x) => x.term);
  assert.ok(terms.includes("photocard"), terms.join(","));
  // 팔린 리스팅에 가장 많이 나온 photocard(8개)가 맨 앞, 겹치는 두 단어 묶음(sealed photocard)은 빠진다
  assert.strictEqual(terms[0], "photocard", terms.join(","));
  assert.ok(!terms.includes("sealed photocard") && !terms.includes("album photocard"), terms.join(","));
  assert.ok(!terms.includes("sealed"));                     // 이미 제목에 있음
  // 제목에 photocard를 넣으면 더는 제안하지 않는다
  const s2 = T.suggestKeywords(res, "NOVA Orbit Album with Photocard Sealed", P.tokens).map((x) => x.term);
  assert.ok(!s2.includes("photocard"));
});

test("제안 단어는 팔린 리스팅 제목에 쓰인 대소문자를 따른다", () => {
  const titles = ["NOVA Orbit Album with Photocard POB", "NOVA Orbit with Photocard POB Sealed", "nova orbit photocard"];
  assert.strictEqual(T.originalCase("photocard", titles), "Photocard");
  assert.strictEqual(T.originalCase("photocard pob", titles), "Photocard POB");
  assert.strictEqual(T.originalCase("zzz", titles), "zzz");   // 없으면 그대로
  assert.strictEqual(T.originalCase("c++", ["C++ book"]), "C++"); // 특수문자 안전
});

console.log(`title-builder.js: ${passed}개 테스트 통과`);
