import asyncio
import unittest

from pages.news.source import (
    Comment,
    HackerNewsService,
    HackerNewsSource,
    Story,
    parse_comment,
    parse_front_page,
)


def immediate(target, args):
    class Thread:
        def start(self):
            target(*args)

    return Thread()


class FrontPageParseTests(unittest.TestCase):
    def payload(self):
        return {
            "hits": [
                {
                    "objectID": "1",
                    "title": "One",
                    "url": "https://www.example.com/a",
                    "points": 10,
                    "num_comments": 2,
                    "author": "alice",
                    "created_at_i": 100,
                },
                {
                    "story_id": 2,
                    "title": None,
                    "points": None,
                    "num_comments": None,
                },
                {"title": "no id"},
            ]
        }

    def test_fields_are_normalised(self):
        stories = parse_front_page(self.payload())
        self.assertEqual(len(stories), 2)
        first = stories[0]
        self.assertEqual(first.id, 1)
        self.assertEqual(first.title, "One")
        self.assertEqual(first.domain, "example.com")
        self.assertEqual(first.points, 10)
        self.assertEqual(first.comments, 2)

    def test_missing_fields_and_ask_hn_fallback(self):
        story = parse_front_page(self.payload())[1]
        self.assertEqual(story.id, 2)
        self.assertEqual(story.title, "(NO TITLE)")
        self.assertEqual(story.points, 0)
        self.assertEqual(story.comments, 0)
        self.assertEqual(story.domain, "HACKER NEWS")

    def test_limit(self):
        self.assertEqual(len(parse_front_page(self.payload(), limit=1)), 1)
        self.assertEqual(parse_front_page(self.payload(), limit=0), [])

    def test_bad_payload(self):
        self.assertEqual(parse_front_page(None), [])
        self.assertEqual(parse_front_page({"hits": None}), [])


class CommentParseTests(unittest.TestCase):
    def test_comment(self):
        comment = parse_comment(
            {"by": "bob", "text": "Hello <b>world</b>", "time": 12}
        )
        self.assertEqual(comment, Comment("bob", "Hello <b>world</b>", 12))

    def test_deleted_dead_and_empty(self):
        self.assertIsNone(parse_comment({"deleted": True, "text": "x"}))
        self.assertIsNone(parse_comment({"dead": True, "text": "x"}))
        self.assertIsNone(parse_comment({"text": "  "}))
        self.assertIsNone(parse_comment(None))


class SourceTests(unittest.TestCase):
    def test_top_comment_skips_deleted_first_kid(self):
        calls = []

        def fake_get_json(url, timeout=None):
            calls.append((url, timeout))
            if url.endswith("/10.json"):
                return {"kids": [11, 12]}
            if url.endswith("/11.json"):
                return {"deleted": True, "text": "gone"}
            if url.endswith("/12.json"):
                return {"by": "carol", "text": "still here", "time": 9}
            raise AssertionError(url)

        source = HackerNewsSource(get_json=fake_get_json, timeout=2.0)
        comment = source.top_comment(10)
        self.assertEqual(comment, Comment("carol", "still here", 9))
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][1], 2.0)

    def test_no_kids(self):
        source = HackerNewsSource(get_json=lambda url, timeout=None: {"kids": []})
        self.assertIsNone(source.top_comment(1))


class ServiceTests(unittest.TestCase):
    def test_front_page_snapshot(self):
        class Source:
            def front_page(self):
                return [Story(1, "One")]

            def top_comment(self, story_id):
                return Comment("bob", "text", 0)

        service = HackerNewsService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        snapshot = service.front_page()
        self.assertTrue(snapshot.loading)
        loaded = service.front_cache.snapshot("front")
        self.assertTrue(loaded.has_value)
        self.assertEqual(loaded.value[0].id, 1)

    def test_comment_snapshot(self):
        class Source:
            def front_page(self):
                return []

            def top_comment(self, story_id):
                return Comment("bob", "text", 0)

        service = HackerNewsService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        service.comment(7)
        loaded = service.comment_cache.snapshot(7)
        self.assertTrue(loaded.has_value)
        self.assertEqual(loaded.value.author, "bob")

    def test_front_page_failure_is_kept_as_an_error(self):
        class Source:
            def front_page(self):
                raise RuntimeError("offline")

            def top_comment(self, story_id):
                return None

        service = HackerNewsService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        service.front_page()
        snapshot = service.front_cache.snapshot("front")
        self.assertFalse(snapshot.has_value)
        self.assertIsInstance(snapshot.error, RuntimeError)

    def test_start_prewarms(self):
        class Source:
            def front_page(self):
                return [Story(1, "One")]

            def top_comment(self, story_id):
                return None

        service = HackerNewsService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        asyncio.run(service.start())
        self.assertTrue(service.front_cache.snapshot("front").has_value)


if __name__ == "__main__":
    unittest.main()
