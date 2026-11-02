// 브라우저용 파서(docs/js/listing-parser.js)를 Node로 실행해 결과를 JSON으로 출력한다.
// tests/test_parser_parity.py 가 파이썬 스크립트 결과와 비교하는 데 쓴다.
// 사용법: node tests/js/run_parser.js 입력파일
const fs = require("fs");
const path = require("path");
const P = require(path.join(__dirname, "..", "..", "docs", "js", "listing-parser.js"));

const file = process.argv[2];
const text = fs.readFileSync(file, "utf8");
const parsed = P.parse(text, file);
const result = P.analyze(parsed.listings);
process.stdout.write(JSON.stringify({ format: parsed.format, listings: parsed.listings, unparsed: parsed.unparsed, ...result }));
