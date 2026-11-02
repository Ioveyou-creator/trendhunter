"""브라우저용 JavaScript 테스트(tests/js/*.test.js)를 파이썬 테스트와 함께 실행.

GitHub Actions 서버에는 Node.js가 기본으로 있어서, 워크플로를 고치지 않아도 매일 함께 돈다.
Node.js가 없는 환경에서는 건너뛴다.
"""

import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which("node")
JS_TESTS = sorted((Path(__file__).resolve().parent / "js").glob("*.test.js"))


@unittest.skipUnless(NODE, "Node.js가 없어 JavaScript 테스트를 건너뜀")
class TestJavaScript(unittest.TestCase):
    def test_js_files(self):
        self.assertTrue(JS_TESTS, "tests/js/*.test.js 가 없음")
        for path in JS_TESTS:
            with self.subTest(path=path.name):
                r = subprocess.run([NODE, str(path)], capture_output=True)
                self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
