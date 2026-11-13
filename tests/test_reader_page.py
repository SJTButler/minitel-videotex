import unittest

import pages
from minitel.data.services import ServiceRegistry
from minitel.pagemodel import LINE_FIELD
from minitel.protocol import codec
from minitel.session import Session
from minitel.terminal.profiles import M1
from pages.common.layout import BODY, SECONDARY, WARNING
from services.common.reader import SearchResult, StaticReaderService
from tests.fixtures.wikipedia import DOCUMENTS, RESULTS

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
GUIDE = bytes([0x13, 0x44])
SUITE = bytes([0x13, 0x48])


def make_session(results=RESULTS):
    registry = pages.build_registry()
    service_registry = ServiceRegistry({
        "wikipedia": StaticReaderService(DOCUMENTS, results),
    })
    page = registry.get("160")
    session = Session(
        registry,
        M1,
        initial="160",
        fallback=page,
        services=service_registry,
    )
    session.start()
    return session


def row(session, number):
    return "".join(cell.ch for cell in session.screen.rows[number])


def find_cell(session, text):
    for line in session.screen.rows:
        value = "".join(cell.ch for cell in line)
        col = value.find(text)
        if col >= 0:
            return line[col]
    raise AssertionError(f"no cell starts {text!r}")


class ReaderPageTests(unittest.TestCase):
    def test_index_renders_fixture_results(self):
        session = make_session()
        text = session.screen.to_text()
        self.assertIn("WIKIPEDIA", text)
        self.assertIn("ALPHA PAGE", text)
        self.assertIn("BETA PAGE", text)
        self.assertIn("GAMMA PAGE", text)
        self.assertIn("WIKIPEDIA. CC BY-SA.", text)
        self.assertEqual(session.current.number, "160")
        field = session.active_field
        self.assertEqual(field.name, LINE_FIELD)
        self.assertTrue(field.live)
        self.assertTrue(field.visible)

    def test_index_search_then_envoi_opens_selected(self):
        session = make_session()
        session.feed(b"BETA PAGE")
        self.assertIn("3 RESULTS", row(session, 4))
        session.feed(ENVOI)  # search
        self.assertEqual(session.current.number, "160")
        self.assertIn("1 RESULT", row(session, 4))
        session.feed(ENVOI)  # open the selected result
        self.assertEqual(session.current.number, "160#BETA")
        self.assertIn("BETA PAGE", session.screen.to_text())
        self.assertFalse(session.active_field.visible)
        self.assertTrue(session.active_field.live)
        self.assertFalse(session.screen.cursor_visible)
        self.assertTrue(row(session, 0).startswith("FIND:"))

    def test_article_one_visible_link_follows(self):
        session = make_session()
        session.navigate("160#BETA")
        session.feed(b"GAMMA")
        self.assertIn("1 ON SCREEN", row(session, 0))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#GAMMA")
        self.assertIn("GAMMA PAGE", session.screen.to_text())

    def test_article_multiple_visible_needs_selection(self):
        session = make_session()
        session.navigate("160#BETA")
        session.feed(b"A")
        self.assertIn("2 ON SCREEN", row(session, 0))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#BETA")
        session.feed(SUITE)
        self.assertIn("1/2", row(session, 0))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#ALPHA")

    def test_article_cycle_wraps(self):
        session = make_session()
        session.navigate("160#BETA")
        session.feed(b"A")
        session.feed(SUITE)
        self.assertIn("1/2", row(session, 0))
        session.feed(SUITE)
        self.assertIn("2/2", row(session, 0))
        session.feed(SUITE)
        self.assertIn("1/2", row(session, 0))
        session.feed(RETOUR)
        self.assertIn("2/2", row(session, 0))

    def test_article_rolls_back_invalid_suffix(self):
        session = make_session()
        session.navigate("160#BETA")
        session.feed(b"GAMMZ")
        self.assertEqual(session.values[LINE_FIELD], "GAMM")
        self.assertIn("1 ON SCREEN", row(session, 0))
        session.feed(b"X")
        self.assertEqual(session.values[LINE_FIELD], "GAMM")

    def test_article_guide_returns_to_index(self):
        session = make_session()
        session.navigate("160#BETA")
        session.feed(GUIDE)
        self.assertEqual(session.current.number, "160")
        self.assertIn("WIKIPEDIA", session.screen.to_text())

    def test_article_retour_returns_to_index_history(self):
        session = make_session()
        session.navigate("160#ALPHA")
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "160")

    def test_index_keeps_arbitrary_query(self):
        session = make_session()
        session.feed(b"ZZZ")
        self.assertEqual(session.values[LINE_FIELD], "ZZZ")
        self.assertIn("3 RESULTS", row(session, 4))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160")
        self.assertEqual(session.values[LINE_FIELD], "ZZZ")
        self.assertIn("NO RESULTS", row(session, 4))
        self.assertTrue(session.screen.rows[6][0].inverse)

    def test_links_use_colour_and_inverse(self):
        session = make_session()
        session.navigate("160#BETA")
        alpha = find_cell(session, "ALPHA")
        self.assertFalse(alpha.underline)
        self.assertEqual(alpha.fg, SECONDARY)
        self.assertFalse(find_cell(session, " ALPHA").underline)
        heading = find_cell(session, "LIST")
        self.assertTrue(heading.inverse)
        self.assertFalse(heading.underline)
        self.assertEqual(heading.fg, BODY)

        session.feed(b"A")
        alpha = find_cell(session, "ALPHA")
        gamma = find_cell(session, "GAMMA")
        self.assertFalse(alpha.underline)
        self.assertFalse(gamma.underline)
        self.assertEqual(alpha.fg, WARNING)
        self.assertEqual(gamma.fg, WARNING)
        self.assertFalse(alpha.inverse)

        session.feed(SUITE)
        self.assertTrue(find_cell(session, "ALPHA").inverse)
        self.assertFalse(find_cell(session, "ALPHA").underline)
        self.assertEqual(find_cell(session, "GAMMA").fg, WARNING)

    def test_index_colour_is_only_on_result_links(self):
        session = make_session()
        title = find_cell(session, "WIKIPEDIA")
        self.assertTrue(title.inverse)
        result = find_cell(session, "BETA PAGE")
        self.assertEqual(result.fg, SECONDARY)
        self.assertFalse(result.inverse)
        self.assertFalse(result.underline)
        self.assertEqual(find_cell(session, "FIXTURE").fg, BODY)
        self.assertEqual(find_cell(session, "ALL PAGES").fg, BODY)
        self.assertEqual(find_cell(session, "3 RESULTS").fg, BODY)
        self.assertEqual(find_cell(session, "SEARCH:").fg, BODY)

    def test_article_colour_is_only_on_links(self):
        session = make_session()
        session.navigate("160#GAMMA")
        heading = find_cell(session, "GAMMA")
        self.assertTrue(heading.inverse)
        self.assertEqual(heading.fg, BODY)
        quote = find_cell(session, "A SHORT QUOTED LINE.")
        self.assertEqual(quote.fg, BODY)
        self.assertFalse(quote.inverse)
        self.assertEqual(find_cell(session, "ALPHA").fg, SECONDARY)
        self.assertEqual(find_cell(session, "BETA").fg, SECONDARY)

    def test_index_suite_crosses_the_outer_page(self):
        results = tuple(
            SearchResult("ALPHA", f"RESULT {index:02d}")
            for index in range(1, 11)
        )
        session = make_session(results)
        session.feed(b"RESULT")
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160")
        self.assertIn("PAGE 1/2", row(session, 20))
        self.assertTrue(find_cell(session, "RESULT 01").inverse)
        for _ in range(7):
            session.feed(SUITE)
        self.assertIn("PAGE 2/2", row(session, 20))
        self.assertTrue(find_cell(session, "RESULT 08").inverse)
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#ALPHA")

    def test_index_empty_envoi_opens_the_selected_result(self):
        session = make_session()
        self.assertTrue(find_cell(session, "ALPHA PAGE").inverse)
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#ALPHA")

    def test_index_guide_restores_query_and_selection(self):
        session = make_session()
        session.feed(b"BETA PAGE")
        session.feed(ENVOI)
        self.assertIn("1 RESULT", row(session, 4))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#BETA")
        session.feed(GUIDE)
        self.assertEqual(session.current.number, "160")
        self.assertEqual(session.values[LINE_FIELD], "BETA PAGE")
        self.assertIn("1 RESULT", row(session, 4))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#BETA")

    def test_anchor_text_matches_target(self):
        session = make_session()
        session.navigate("160#ALPHA")
        session.feed(b"LINK TO GAMMA")
        self.assertIn("1 ON SCREEN", row(session, 0))
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "160#GAMMA")

    def test_fixture_labels_cover_anchor_text(self):
        for document in DOCUMENTS.values():
            for block in document.blocks:
                for span in block.spans:
                    if span.link is None:
                        continue
                    link = document.links[span.link]
                    labels = [label.casefold() for label in link.labels]
                    self.assertIn(
                        span.text.casefold(), labels,
                        (document.token, span.text),
                    )

    def test_article_uses_cell_paint_and_index_stays_row(self):
        session = make_session()
        self.assertIsNone(session.screen.paint)
        session.navigate("160#BETA")
        self.assertEqual(session.screen.paint, "cell")

    def test_find_highlight_does_not_clear_link_rows(self):
        session = make_session()
        session.navigate("160#BETA")
        actions = session.feed(b"A")
        raw = b"".join(action.raw for action in actions)
        self.assertNotIn(bytes([codec.CAN]), raw)
        self.assertIn("ALPHA", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
