import unittest
from urllib.parse import parse_qs, urlparse

from pages.common.reader import render_lines
from services.common.reader import find_links
from services.wikipedia.html import parse_html
from services.wikipedia.source import (
    WikipediaSource,
    from_base36,
    parse_article,
    parse_search,
    to_base36,
)

ARTICLE_HTML = """
<div class="mw-parser-output">
  <p>LEAD <a href="/wiki/Alan_Turing" title="Alan Turing">TURING</a>
     AND <a href="/wiki/Computing">COMPUTING</a>.</p>
  <h2><span class="mw-headline">EARLY LIFE</span></h2>
  <p>MORE <a href="/wiki/File:Photo.jpg">PHOTO</a>
     <a href="/wiki/Category:People">CATEGORY</a>
     <a href="https://example.com">EXTERNAL</a>.</p>
  <table><tr><td>HIDDEN TABLE</td></tr></table>
  <p>VISIBLE <sup class="reference">[1]</sup> END.</p>
  <ul><li>ONE</li><li>TWO <a href="/wiki/Logic">LOGIC</a></li></ul>
  <blockquote><p>QUOTE</p></blockquote>
  <pre>CODE
LINE</pre>
</div>
"""


def _payload(action, params):
    if action == "parse":
        return {
            "parse": {
                "title": "Alan Turing",
                "pageid": 123,
                "revid": 77,
                "text": ARTICLE_HTML,
            }
        }
    if params.get("list") == ["search"]:
        return {
            "query": {
                "search": [
                    {
                        "pageid": 123,
                        "title": "Alan Turing",
                        "snippet": '<span class="searchmatch">Alan</span> Turing',
                    },
                    {
                        "pageid": 456,
                        "title": "Computing",
                        "snippet": "Computing",
                    },
                ]
            }
        }
    titles = params.get("titles", [""])[0].split("|")
    pages = []
    for title in titles:
        if title == "Computing":
            pages.append({
                "pageid": 456, "ns": 0, "title": "Computing"
            })
        elif title == "Logic":
            pages.append({
                "pageid": 789, "ns": 0, "title": "Logic"
            })
        else:
            pages.append({
                "pageid": 999, "ns": 0, "title": title
            })
    return {"query": {"pages": pages}}


class FakeHttp:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers=None, timeout=None):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        action = params.get("action", [""])[0]
        self.calls.append((action, params))
        return _payload(action, params)


class Base36Tests(unittest.TestCase):
    def test_roundtrip(self):
        for value in (0, 1, 123, 456, 789, 999, 12345678):
            self.assertEqual(from_base36(to_base36(value)), value)
        self.assertEqual(to_base36(123), "3F")
        self.assertEqual(to_base36(456), "CO")
        self.assertIsNone(from_base36("!"))
        self.assertIsNone(from_base36(""))


class ParserTests(unittest.TestCase):
    def test_blocks_and_links(self):
        blocks = parse_html(ARTICLE_HTML)
        kinds = [block.kind for block in blocks]
        self.assertEqual(kinds[0], "body")
        self.assertIn("heading", kinds)
        self.assertIn("bullet", kinds)
        self.assertIn("quote", kinds)
        self.assertIn("code", kinds)
        text = " ".join(
            span.text for block in blocks for span in block.spans
        )
        self.assertIn("LEAD", text)
        self.assertNotIn("HIDDEN TABLE", text)
        self.assertNotIn("[1]", text)
        self.assertIn("QUOTE", text)
        self.assertIn("CODE\nLINE", text)
        targets = [
            span.target for block in blocks for span in block.spans
            if span.target
        ]
        self.assertIn("Alan Turing", targets)
        self.assertIn("Computing", targets)
        self.assertIn("Logic", targets)
        self.assertNotIn("File:Photo.jpg", targets)
        self.assertNotIn("Category:People", targets)

    def test_search_and_article_payloads(self):
        search = parse_search(_payload("query", {"list": ["search"]}))
        self.assertEqual([result.token for result in search], ["3F", "CO"])
        article = parse_article(_payload("parse", {}))
        self.assertEqual(article.title, "ALAN TURING")
        self.assertEqual(article.pageid, 123)
        self.assertEqual(article.revid, 77)
        self.assertIsNone(parse_article({"error": {"code": "missing"}}))


class SourceTests(unittest.TestCase):
    def test_document_resolves_links_and_keeps_labels(self):
        http = FakeHttp()
        source = WikipediaSource(get_json=http)
        document = source.document("3F")
        self.assertIsNotNone(document)
        self.assertEqual(document.token, "3F")
        self.assertEqual(document.title, "ALAN TURING")
        self.assertEqual(document.revision, "77")
        links = {link.token: link for link in document.links}
        self.assertIn("CO", links)       # Computing
        self.assertIn("LX", links)       # Logic (789)
        self.assertEqual(links["CO"].labels, ("COMPUTING",))
        self.assertEqual(
            find_links(document, "computing"), (0,)
        )
        self.assertNotIn("3F", links)    # self link
        text = "\n".join(line.text for line in render_lines(document))
        self.assertIn("LEAD TURING AND COMPUTING.", text)
        # The article parse is followed by a title-resolution batch.
        self.assertTrue(any(action == "query" for action, _ in http.calls))

    def test_search_and_empty(self):
        source = WikipediaSource(get_json=FakeHttp())
        results = source.search("alan")
        self.assertEqual([result.token for result in results], ["3F", "CO"])
        self.assertEqual(results[0].title, "ALAN TURING")
        self.assertEqual(source.search(""), ())
        self.assertIsNone(source.document("!"))
        self.assertIsNone(source.document(""))


if __name__ == "__main__":
    unittest.main()
