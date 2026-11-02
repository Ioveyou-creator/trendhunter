"""파이썬 분석 스크립트(스킬)와 브라우저 분석기(JavaScript)가 같은 결과를 내는지 확인.

두 구현은 같은 규칙을 각자 다른 언어로 갖고 있어서, 한쪽만 고치면 결과가 어긋날 수 있다.
이 테스트가 그걸 잡는다. Node.js가 없으면 건너뛴다 (GitHub Actions 서버에는 기본 설치되어 있음).
"""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "ebay-seo-lens"
spec = importlib.util.spec_from_file_location("analyze_listings", SKILL / "scripts" / "analyze_listings.py")
al = importlib.util.module_from_spec(spec)
spec.loader.exec_module(al)

NODE = shutil.which("node")

FIXTURES = [
    ROOT / "tests" / "fixtures" / "real" / "pokemon_mobile_kr_2026-11-02.txt",
    SKILL / "evals" / "kpop-photocard-keyword" / "files" / "nova_orbit.txt",
    SKILL / "evals" / "tcg-shipping-confound" / "files" / "starlight_box.csv",
    SKILL / "evals" / "small-sample-holds-back" / "files" / "lumi_lightstick.txt",
]


def python_result(path: Path) -> dict:
    listings, unparsed, fmt = al.parse(path.read_text(encoding="utf-8"), path.name)
    return json.loads(json.dumps({"format": fmt, "listings": listings, "unparsed": unparsed, **al.analyze(listings)}))


def js_result(path: Path) -> dict:
    out = subprocess.run([NODE, str(ROOT / "tests" / "js" / "run_parser.js"), str(path)],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


@unittest.skipUnless(NODE, "Node.js가 없어 브라우저 파서 비교를 건너뜀")
class TestParity(unittest.TestCase):
    def assertSame(self, path: Path):
        py, js = python_result(path), js_result(path)
        self.assertEqual(py["listings"], js["listings"], f"{path.name}: 리스팅 파싱 결과가 다름")
        self.assertEqual(py, js, f"{path.name}: 분석 결과가 다름")

    def test_fixtures(self):
        for path in FIXTURES:
            with self.subTest(path=path.name):
                self.assertSame(path)

    def test_rounding_edge(self):
        # 16개 중 1개 판매 = 0.0625. 파이썬 round()라면 0.062, JS Math.round라면 0.063이 되는 경계값
        rows = ["title,price,shipping,status"] + [
            f"Edge Item {'Alpha' if i == 0 else 'Beta'} Gamma,{10 + i}.005,0,{'sold' if i == 0 else 'unsold'}"
            for i in range(16)
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        try:
            self.assertSame(Path(f.name))
            self.assertEqual(python_result(Path(f.name))["counts"]["sell_through"], 0.063)
        finally:
            Path(f.name).unlink()


if __name__ == "__main__":
    unittest.main()
