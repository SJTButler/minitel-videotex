import time
import unittest

import pages

from minitel import codec, profiles
from minitel.cache import Snapshot
from minitel.render import render
from minitel.session import Session
from pages.layout import ACCENT, SECONDARY
from services.news import Comment, Story
from test_render import decode

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SOMMAIRE = bytes([0x13, 0x46])
SUITE = bytes([0x13, 0x48])


def loaded(value):
    return Snapshot(value=value, loaded_at=time.monotonic())


def stories(count):
    now = int(time.time())
    return [
        Story(
            id=index,
            title=f"STORY {index}",
            url=f"https://www.site{index}.com/a",
            points=100 + index,
            comments=10 + index,
            author="alice",
            created_at=now - 3600,
        )
        for index in range(1, count + 1)
    ]


class FakeService:
    def __init__(self, front=None, comments=None, front_sequence=None):
        self.front = front
        self.front_sequence = list(front_sequence or [])
        self.comments = comments or {}
        self.comment_sequence = {}
        self.front_calls = 0
        self.comment_calls = 0

    def front_page(self):
        self.front_calls += 1
        if self.front_sequence:
            index = min(self.front_calls - 1, len(self.front_sequence) - 1)
            return self.front_sequence[index]
        return self.front

    def comment(self, story_id):
        self.comment_calls += 1
        sequence = self.comment_sequence.get(story_id)
        if sequence:
            index = min(self.comment_calls - 1, len(sequence) - 1)
            return sequence[index]
        return self.comments.get(story_id, Snapshot(loading=True))


def make_session(service=None, initial="111"):
    registry = pages.build_registry()
    session = Session(
        registry,
        profiles.M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        services={"hackernews": service} if service is not None else None,
    )
    session.start()
    session.navigate(initial)
    return session


class ListTests(unittest.TestCase):
    def test_list_layout(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service)
        text = session.screen.to_text().splitlines()

        self.assertIn("111 1/2", text[0])
        self.assertEqual(text[1].strip(), "HACKER NEWS")
        self.assertTrue(text[2].startswith("FRONT PAGE"))
        self.assertTrue(text[3].startswith("1 STORY 1"))
        self.assertTrue(text[7].startswith("2 STORY 2"))
        self.assertTrue(text[11].startswith("3 STORY 3"))
        self.assertTrue(text[15].startswith("4 STORY 4"))
        self.assertIn("SITE4.COM", text[17])
        self.assertIn("104P", text[17])
        self.assertIn("14C", text[17])
        self.assertEqual(text[18].strip(), "TYPE 1-4, THEN ENVOI")
        self.assertTrue(text[22].startswith("SUITE=NEXT"))
        self.assertEqual(text[23].strip(), "1-4 + ENVOI = STORY")
        self.assertNotIn("STORY 5", session.screen.to_text())

        self.assertEqual(session.screen.rows[3][0].fg, ACCENT)
        self.assertTrue(session.screen.rows[3][0].inverse)
        self.assertEqual(session.screen.rows[5][2].fg, SECONDARY)
        self.assertTrue(session.screen.rows[5][2].underline)
        self.assertTrue(
            any(
                cell.fg == ACCENT and cell.underline
                for cell in session.screen.rows[5]
            )
        )

        decoded = decode(render(session.screen))
        self.assertEqual(decoded.rows[3][0].ch, "1")
        self.assertTrue(decoded.rows[3][0].inverse)
        self.assertFalse(decoded.rows[3][1].inverse)
        self.assertFalse(decoded.rows[3][2].inverse)
        self.assertFalse(decoded.rows[3][3].inverse)

    def test_select_story_opens_detail(self):
        service = FakeService(front=loaded(stories(5)))
        session = make_session(service)
        session.feed(b"1" + ENVOI)

        self.assertEqual(session.current.number, "112")
        self.assertEqual(session.state["news_story"].id, 1)
        text = session.screen.to_text().splitlines()
        self.assertIn("STORY 1", text[3])
        self.assertIn("SITE1.COM", text[6])
        self.assertIn("11 COMMENTS", text[7])
        self.assertIn("LOADING COMMENT...", session.screen.to_text())

    def test_suite_advances_and_wraps(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service)
        session.feed(SUITE)
        self.assertEqual(session.pager.offset, 4)
        self.assertEqual(session.current.number, "111")
        self.assertIn("111 2/2", session.screen.to_text().splitlines()[0])
        self.assertTrue(
            session.screen.to_text().splitlines()[3].startswith("1 STORY 5")
        )

        session.feed(SUITE)
        self.assertEqual(session.pager.offset, 0)
        self.assertIn("111 1/2", session.screen.to_text().splitlines()[0])

    def test_retour_pages_back_then_leaves(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service, initial="110")
        session.navigate("111")
        session.feed(SUITE)
        self.assertEqual(session.pager.offset, 4)

        session.feed(b"1")
        self.assertEqual(session.line, "1")
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "111")
        self.assertEqual(session.pager.offset, 0)
        self.assertEqual(session.line, "")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "110")

    def test_pager_position_survives_detail(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service, initial="110")
        session.navigate("111")
        session.feed(SUITE)
        self.assertEqual(session.pager.label, "2/2")

        session.feed(b"1" + ENVOI)
        self.assertEqual(session.current.number, "112")
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "111")
        self.assertEqual(session.pager.label, "2/2")

    def test_pager_position_survives_sommaire(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service, initial="110")
        session.navigate("111")
        session.feed(SUITE)
        self.assertEqual(session.pager.label, "2/2")

        session.feed(SOMMAIRE)
        self.assertEqual(session.current.number, "100")
        session.navigate("110")
        session.navigate("111")
        self.assertEqual(session.pager.label, "2/2")

        session.feed(RETOUR)
        self.assertEqual(session.pager.label, "1/2")

    def test_suite_clears_typed_input(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service)
        session.feed(b"1")
        self.assertEqual(session.line, "1")
        session.feed(SUITE)
        self.assertEqual(session.line, "")
        self.assertEqual(session.pager.offset, 4)

    def test_invalid_story_number_stays(self):
        service = FakeService(front=loaded(stories(5)))
        session = make_session(service)
        session.feed(b"5" + ENVOI)
        self.assertEqual(session.current.number, "111")
        self.assertIn("NO STORY 5.", session.screen.to_text())

        session.feed(b"9" + ENVOI)
        self.assertEqual(session.current.number, "111")
        self.assertIn("NO STORY 9.", session.screen.to_text())

    def test_full_page_number_still_routes(self):
        service = FakeService(front=loaded(stories(5)))
        session = make_session(service)
        session.feed(b"120" + ENVOI)
        self.assertEqual(session.current.number, "120")

    def test_offline_keeps_cached_stories(self):
        snapshot = Snapshot(
            value=stories(5),
            loaded_at=time.monotonic(),
            error=RuntimeError("offline"),
        )
        session = make_session(FakeService(front=snapshot))
        text = session.screen.to_text()
        self.assertIn("STORY 1", text)
        self.assertIn("OFFLINE. 1-4 + ENVOI", text)
        self.assertIn("FRONT PAGE  OFFLINE", text)

    def test_missing_service_renders_unavailable(self):
        session = make_session(None)
        text = session.screen.to_text()
        self.assertIn("NEWS UNAVAILABLE.", text)
        self.assertIn("CHECK CONNECTION, THEN", text)
        self.assertIn("RETRYING AUTOMATICALLY.", text)

    def test_unicode_titles_render(self):
        story = Story(1, "\u2018Hello\u2019 \U0001f680 \u2014 world")
        service = FakeService(front=loaded([story]))
        session = make_session(service)
        text = session.screen.to_text()
        self.assertIn("'HELLO' - WORLD", text)
        render(session.screen)

    def test_list_tick_diff_restores_cursor(self):
        service = FakeService(
            front_sequence=[Snapshot(loading=True), loaded(stories(5))]
        )
        session = make_session(service)
        self.assertIn("FETCHING HACKER NEWS", session.screen.to_text())

        action = session.tick()
        self.assertIn(codec.pos(20, 6), action.raw)
        self.assertIn(codec.cursor(False), action.raw)
        self.assertIn("STORY 1", session.screen.to_text())
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col), (20, 6)
        )


class DetailTests(unittest.TestCase):
    def test_metadata_and_comment(self):
        now = int(time.time())
        story = Story(
            1, "A TITLE", "https://www.example.com/a",
            points=42, comments=3, author="alice", created_at=now - 3600,
        )
        comment = Comment(
            "bob", "This is a <b>comment</b> &amp; more", now - 600
        )
        service = FakeService(
            front=loaded([story]),
            comments={1: loaded(comment)},
        )
        session = make_session(service)
        session.feed(b"1" + ENVOI)
        text = session.screen.to_text().splitlines()

        self.assertIn("A TITLE", text[3])
        self.assertIn("EXAMPLE.COM  42 POINTS", text[6])
        self.assertIn("3 COMMENTS  BY ALICE  1H", text[7])
        self.assertEqual(text[9].strip(), "TOP COMMENT")
        self.assertIn("THIS IS A COMMENT & MORE", text[10])
        self.assertIn("- BOB", text[19])

        screen = session.screen
        self.assertEqual(screen.rows[6][0].fg, SECONDARY)
        self.assertTrue(screen.rows[6][0].underline)
        self.assertEqual(screen.rows[6][13].fg, ACCENT)
        self.assertTrue(screen.rows[6][13].underline)
        self.assertEqual(screen.rows[7][0].fg, ACCENT)
        self.assertTrue(screen.rows[7][0].underline)
        self.assertEqual(screen.rows[7][10].fg, SECONDARY)
        self.assertTrue(screen.rows[7][10].underline)
        self.assertTrue(screen.rows[9][0].inverse)
        self.assertEqual(screen.rows[19][0].fg, SECONDARY)
        self.assertTrue(screen.rows[19][0].underline)

    def test_zero_comments_does_not_fetch(self):
        story = Story(1, "NO TALK", comments=0)
        service = FakeService(front=loaded([story]))
        session = make_session(service)
        session.state["news_story"] = story
        session.navigate("112")
        self.assertIn("NO COMMENTS YET.", session.screen.to_text())
        self.assertEqual(service.comment_calls, 0)

    def test_manual_detail_retour_goes_to_list_then_history(self):
        service = FakeService(front=loaded(stories(6)))
        session = make_session(service, initial="112")
        self.assertEqual(session.current.number, "112")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "111")
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "100")

    def test_direct_detail_has_no_story(self):
        session = make_session(FakeService(front=loaded([])), initial="112")
        text = session.screen.to_text()
        self.assertIn("NO STORY SELECTED.", text)
        self.assertIn("OPEN NEWS, PICK 1-4.", text)

    def test_comment_loads_on_tick(self):
        story = Story(1, "A TITLE", comments=2)
        service = FakeService(front=loaded([story]))
        service.comment_sequence[1] = [
            Snapshot(loading=True),
            loaded(Comment("bob", "LATE COMMENT", 0)),
        ]
        session = make_session(service)
        session.state["news_story"] = story
        session.navigate("112")
        self.assertIn("LOADING COMMENT...", session.screen.to_text())

        session.tick()
        self.assertIn("LATE COMMENT", session.screen.to_text())
        self.assertIn("- BOB", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
