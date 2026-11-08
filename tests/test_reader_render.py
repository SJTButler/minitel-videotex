import unittest

from pages.common.reader import (
    Line,
    LineSpan,
    build_stops,
    find_results,
    render_lines,
    starts_for,
    visible_matches,
)
from services.common.reader import (
    Block,
    Document,
    Link,
    SearchResult,
    Span,
    StaticReaderService,
    find_links,
    match_prefix,
)

LINKS = (
    Link("BETA", "BETA PAGE", ("BETA", "THE BETA PAGE")),
    Link("GAMMA", "GAMMA PAGE", ("GAMMA",)),
)
DOCUMENT = Document(
    "ALPHA",
    "ALPHA PAGE",
    (
        Block("heading", (Span("WELCOME"),), 2),
        Block(
            "paragraph",
            (
                Span("ALPHA LINKS TO "),
                Span("BETA", 0),
                Span(" AND "),
                Span("GAMMA", 1),
            ),
        ),
        Block(
            "paragraph",
            (
                Span("TARGET TITLE MATCH: "),
                Span("HERE", 1),
            ),
        ),
        Block("bullet", (Span("BULLET"),)),
        Block("quote", (Span("QUOTE"),)),
    ),
    links=LINKS,
    credit="CREDIT",
)


class ReaderModelTests(unittest.TestCase):
    def test_find_links_and_prefix(self):
        self.assertEqual(find_links(DOCUMENT, "beta"), (0,))
        self.assertEqual(find_links(DOCUMENT, "gamma"), (1,))
        self.assertEqual(find_links(DOCUMENT, "beta page"), (0,))
        self.assertEqual(find_links(DOCUMENT, "nope"), ())
        self.assertEqual(find_links(DOCUMENT, ""), ())
        self.assertEqual(match_prefix(DOCUMENT, "betax"), ("beta", (0,)))
        self.assertEqual(match_prefix(DOCUMENT, "zzz"), ("", ()))

    def test_render_lines_preserves_links(self):
        lines = render_lines(DOCUMENT)
        self.assertEqual(lines[0].kind, "title")
        self.assertEqual(lines[0].text, "ALPHA PAGE")
        body = next(line for line in lines if "BETA" in line.text)
        spans = {
            span.text: span.link for span in body.spans
            if span.link is not None
        }
        self.assertEqual(spans["BETA"], 0)
        self.assertEqual(spans["GAMMA"], 1)
        self.assertTrue(all(len(line.text) <= 39 for line in lines))
        self.assertEqual(lines[-1].kind, "credit")

    def test_visible_matches_and_stops(self):
        lines = render_lines(DOCUMENT)
        window = lines[:6]
        visible = visible_matches((0, 1), window)
        self.assertEqual(visible, (0, 1))
        stops = build_stops((0, 1), lines, 0, 6)
        self.assertEqual([stop.link for stop in stops], [0, 1])
        self.assertEqual(stops[0].first_line, 4)
        self.assertEqual(stops[1].first_line, 4)

    def test_starts_for_visible_and_direction(self):
        stops = build_stops(
            (0, 1),
            (
                Line("body", (LineSpan("BETA", 0),)),
                Line("body", (LineSpan("GAMMA", 1),)),
            ),
            0,
            2,
        )
        self.assertEqual(starts_for(stops, (0,), offset=0, height=2), (0, 0))
        self.assertEqual(starts_for(stops, (), offset=0, height=2), (0, 1))
        self.assertEqual(starts_for(stops, (), offset=3, height=2), (0, 1))

    def test_static_service_and_results(self):
        result = SearchResult("ALPHA", "ALPHA PAGE", "SNIPPET", "TAG")
        service = StaticReaderService({"ALPHA": DOCUMENT}, (result,))
        self.assertIs(service.document("alpha").value, DOCUMENT)
        self.assertIsNone(service.document("missing").value)
        self.assertEqual(service.search("alpha").value, (result,))
        self.assertEqual(service.search("nope").value, ())
        self.assertEqual(find_results((result,), "alpha"), (result,))
        self.assertEqual(find_results((result,), "nope"), ())


if __name__ == "__main__":
    unittest.main()
