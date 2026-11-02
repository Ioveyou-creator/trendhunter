"""웹사이트 기본 SEO 점검 (15단계).

Lighthouse SEO 점수는 개편 전에도 네 페이지 모두 100이라 개선을 보여주지 못한다.
그래서 Lighthouse가 보지 않는 항목(공유 미리보기, 대표 주소, 사이트맵, 구조화 정보)을 직접 확인한다.
표준 라이브러리만 사용.
"""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
BASE = "https://ioveyou-creator.github.io/trendhunter/"
PAGES = {"index.html": BASE, "opportunity.html": BASE + "opportunity.html",
         "analyzer.html": BASE + "analyzer.html", "title.html": BASE + "title.html"}


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.links, self.title, self.ld = {}, {}, "", []
        self._in_title = self._in_ld = False
        self.lang = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "meta":
            key = a.get("name") or a.get("property") or a.get("http-equiv")
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "link" and a.get("rel"):
            self.links[a["rel"]] = a.get("href")
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.ld.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.ld[-1] += data


def parse(name):
    h = Head()
    h.feed((DOCS / name).read_text(encoding="utf-8"))
    return h


class TestPageHead(unittest.TestCase):
    def test_each_page(self):
        titles = set()
        for name, url in PAGES.items():
            with self.subTest(page=name):
                h = parse(name)
                self.assertEqual(h.lang, "ko")
                self.assertTrue(10 <= len(h.title) <= 60, h.title)
                titles.add(h.title)
                desc = h.meta.get("description", "")
                self.assertTrue(40 <= len(desc) <= 160, f"설명 길이 {len(desc)}")
                self.assertEqual(h.links.get("canonical"), url)
                self.assertEqual(h.meta.get("og:url"), url)
                self.assertEqual(h.meta.get("og:title"), h.title)
                self.assertTrue(h.meta.get("og:description"))
                self.assertEqual(h.meta.get("og:image"), BASE + "og-image.png")
                self.assertEqual(h.meta.get("twitter:card"), "summary_large_image")
                self.assertEqual(h.links.get("icon"), "favicon.svg")
                # 외부로 데이터를 보내지 않는다는 약속 유지
                self.assertIn("connect-src 'self'", h.meta.get("Content-Security-Policy", ""))
        self.assertEqual(len(titles), len(PAGES), "페이지 제목이 겹침")

    def test_json_ld(self):
        h = parse("index.html")
        self.assertEqual(len(h.ld), 1)
        data = json.loads(h.ld[0])
        self.assertEqual(data["@type"], "WebApplication")
        self.assertEqual(data["url"], BASE)

    def test_files_exist(self):
        for f in ["og-image.png", "favicon.svg", "sitemap.xml"]:
            self.assertTrue((DOCS / f).exists(), f)
        png = (DOCS / "og-image.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        w, hgt = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        self.assertEqual((w, hgt), (1200, 630))


class TestSitemap(unittest.TestCase):
    def test_lists_every_page(self):
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ET.parse(DOCS / "sitemap.xml").getroot()
        locs = sorted(e.text for e in root.findall("s:url/s:loc", ns))
        self.assertEqual(locs, sorted(PAGES.values()))

    def test_every_html_is_in_sitemap(self):
        html = sorted(p.name for p in DOCS.glob("*.html"))
        self.assertEqual(html, sorted(PAGES))


class TestDashboardScripts(unittest.TestCase):
    def test_no_inline_script(self):
        # CSP가 script-src 'self' 라 인라인 스크립트는 막힌다 (JSON-LD 데이터 블록만 허용)
        for name in PAGES:
            s = (DOCS / name).read_text(encoding="utf-8")
            for m in re.finditer(r"<script([^>]*)>(.*?)</script>", s, re.S):
                attrs, body = m.group(1), m.group(2).strip()
                if body:
                    self.assertIn('type="application/ld+json"', attrs, name)


if __name__ == "__main__":
    unittest.main()
