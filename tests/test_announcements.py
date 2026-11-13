import unittest
from datetime import datetime, timezone

from diagnostics_pages.announce import (
    ANNOUNCE_ON,
    ANNOUNCE_STARTED,
    INTERVAL,
    _announce,
)
from minitel import (
    AnnounceContext,
    Announcement,
    AnnouncementPolicy,
    FunctionPage,
    M1,
    Registry,
    Screen,
    Session,
)
from pages.sports._support.announcements import (
    SPORTS_CHANNEL,
    collect_goal_alerts,
)
from services.sports.models import Alert, FeedSnapshot, alert_key
from run_server import override_report


def render(ctx):
    return Screen()


def provider(ctx):
    return ()


def provider_two(ctx):
    return ()


def make_alert(kind="GOAL", minute=72, injury_time=None):
    return Alert(
        datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc),
        kind,
        1,
        "ARS",
        "CHE",
        1,
        0,
        minute,
        injury_time,
        "PL",
    )


class FakeFeed:
    def __init__(self, snapshot):
        self.configured = True
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


class FakeContext:
    def __init__(self, services=None, *, state=None, now=0.0):
        self._services = services or {}
        self.state = state if state is not None else {}
        self.now = now

    def service(self, name, default=None):
        return self._services.get(name, default)


class AnnouncementValueTests(unittest.TestCase):
    def test_policy_defaults(self):
        policy = AnnouncementPolicy()
        self.assertEqual(policy.show, 12.0)
        self.assertEqual(policy.gap, 4.0)
        self.assertEqual(policy.poll, 5.0)
        self.assertEqual(policy.capacity, 8)
        self.assertTrue(policy.enabled)
        self.assertTrue(policy.on_screensaver)

    def test_announcement_value(self):
        value = Announcement("goal:1", "GOAL ARS 1-0 CHE", at=1.0)
        self.assertEqual(value.key, "goal:1")
        self.assertEqual(value.text, "GOAL ARS 1-0 CHE")


class PageDeclarationTests(unittest.TestCase):
    def test_announce_and_channel_are_stored(self):
        page = FunctionPage(
            "900",
            render,
            requires=("sports",),
            announce=provider,
            announce_channel="sports",
        )
        self.assertIs(page.announce, provider)
        self.assertEqual(page.announce_channel, "sports")

    def test_channel_defaults_to_the_page_number(self):
        page = FunctionPage("901", render, announce=provider)
        self.assertIsNone(page.announce_channel)

        registry = Registry()
        registry.add(page)
        self.assertEqual(registry.announcers(), (("901", page, provider),))

    def test_channel_requires_a_provider(self):
        with self.assertRaises(ValueError):
            FunctionPage("902", render, announce_channel="sports")

    def test_invalid_declarations_are_rejected(self):
        with self.assertRaises(TypeError):
            FunctionPage("903", render, announce=object())
        with self.assertRaises(TypeError):
            FunctionPage(
                "903", render, announce=provider, announce_channel=""
            )
        with self.assertRaises(TypeError):
            FunctionPage(
                "903", render, announce=provider, announce_channel="bad/sports"
            )


class ChannelResolutionTests(unittest.TestCase):
    def test_later_package_replaces_a_channel_without_the_page(self):
        public = FunctionPage(
            "150", render, announce=provider, announce_channel="sports"
        )
        private = FunctionPage(
            "810", render, announce=provider_two, announce_channel="sports"
        )
        registry = Registry()
        registry.add(public, source="public")
        registry.add(private, source="private", on_conflict="override")

        self.assertEqual(
            registry.announcers(), (("sports", private, provider_two),)
        )
        self.assertIs(registry.get("150"), public)
        events = [
            event for event in registry.overrides
            if event.kind == "announcement"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].key, "sports")
        self.assertIn(
            "announcement channel sports",
            override_report(registry),
        )

    def test_same_package_channels_are_fatal(self):
        registry = Registry()
        registry.add(
            FunctionPage(
                "150", render, announce=provider, announce_channel="sports"
            ),
            source="public",
        )
        with self.assertRaises(ValueError):
            registry.add(
                FunctionPage(
                    "810", render, announce=provider_two,
                    announce_channel="sports",
                ),
                source="public",
                on_conflict="override",
            )

    def test_error_mode_rejects_a_channel_collision(self):
        registry = Registry()
        registry.add(
            FunctionPage(
                "150", render, announce=provider, announce_channel="sports"
            ),
            source="public",
        )
        with self.assertRaises(ValueError):
            registry.add(
                FunctionPage(
                    "810", render, announce=provider_two,
                    announce_channel="sports",
                ),
                source="private",
            )

    def test_different_channels_both_contribute(self):
        registry = Registry()
        sports = FunctionPage(
            "150", render, announce=provider, announce_channel="sports"
        )
        espn = FunctionPage(
            "810", render, announce=provider_two, announce_channel="espn"
        )
        registry.add(sports, source="public")
        registry.add(espn, source="private", on_conflict="override")
        self.assertEqual(
            registry.announcers(),
            (("espn", espn, provider_two), ("sports", sports, provider)),
        )

    def test_replacing_a_page_without_announce_removes_its_source(self):
        registry = Registry()
        sporty = FunctionPage(
            "150", render, announce=provider, announce_channel="sports"
        )
        plain = FunctionPage("150", render)
        registry.add(sporty, source="public")
        registry.add(plain, source="private", on_conflict="override")
        self.assertEqual(registry.announcers(), ())
        self.assertIs(registry.get("150"), plain)


class ContextTests(unittest.TestCase):
    def test_service_requires_the_page_declaration(self):
        class Session:
            state = {}
            services = {"sports": object()}

            @staticmethod
            def wall_clock():
                return 12.0

        page = FunctionPage("904", render, requires=("sports",))
        ctx = AnnounceContext(Session(), page)
        self.assertIs(ctx.service("sports"), Session.services["sports"])
        self.assertEqual(ctx.now, 12.0)
        with self.assertRaises(KeyError):
            ctx.service("missing")


class SportsProviderTests(unittest.TestCase):
    def test_only_goals_are_returned(self):
        goal = make_alert("GOAL", 72)
        kickoff = make_alert("KO", None)
        snapshot = FeedSnapshot(
            alerts=(goal, kickoff), loaded_at=1.0
        )
        ctx = FakeContext({"sports": FakeFeed(snapshot)})
        values = collect_goal_alerts(ctx)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].key, alert_key(goal))
        self.assertEqual(values[0].text, "GOAL ARS 1-0 CHE 72'")
        self.assertEqual(values[0].at, goal.at.timestamp())
        self.assertEqual(SPORTS_CHANNEL, "sports")

    def test_unconfigured_or_empty_feed_returns_nothing(self):
        self.assertEqual(collect_goal_alerts(FakeContext()), ())
        snapshot = FeedSnapshot()
        ctx = FakeContext({"sports": FakeFeed(snapshot)})
        self.assertEqual(collect_goal_alerts(ctx), ())


class DiagnosticsProviderTests(unittest.TestCase):
    def test_off_emits_nothing(self):
        self.assertEqual(_announce(FakeContext(now=100.0)), ())

    def test_on_emits_one_announcement_per_bucket(self):
        ctx = FakeContext(
            state={ANNOUNCE_ON: True, ANNOUNCE_STARTED: 100.0},
            now=100.0,
        )
        first = _announce(ctx)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].text, "TEST ANNOUNCEMENT 1")

        ctx.now = 100.0 + INTERVAL
        second = _announce(ctx)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].text, "TEST ANNOUNCEMENT 2")
        self.assertNotEqual(first[0].key, second[0].key)


class AnnouncementPollingLogTests(unittest.TestCase):
    class Clock:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

    def make_session(self, provider, *, policy=None):
        clock = self.Clock()
        log = []
        page = FunctionPage("950", render, announce=provider)
        registry = Registry()
        registry.add(page)
        session = Session(
            registry,
            M1,
            initial="950",
            fallback=page,
            announcement_policy=policy or AnnouncementPolicy(poll=5.0),
            clock=clock,
            wall_clock=clock,
            log=log.append,
        )
        session.start()
        return session, clock, log

    def test_poll_logs_only_new_callers_without_text(self):
        events = []

        def provider(ctx):
            return tuple(events)

        session, clock, log = self.make_session(provider)
        self.assertEqual(session.next_timeout(), 0.0)
        session.on_timeout()
        self.assertEqual(log, [])

        clock.advance(5.0)
        events.append(Announcement("k", "SECRET TEXT", at=5.0))
        session.on_timeout()
        self.assertTrue(
            any("ANNOUNCE 950 <- 950: 1 new" in line for line in log)
        )
        self.assertFalse(any("SECRET TEXT" in line for line in log))

        clock.advance(5.0)
        session.on_timeout()
        self.assertEqual(
            len([line for line in log if "ANNOUNCE 950 <- 950" in line]), 1
        )

    def test_backfilled_announcements_are_not_logged_as_new(self):
        events = []

        def provider(ctx):
            return tuple(events)

        session, clock, log = self.make_session(provider)
        session.on_timeout()

        clock.advance(5.0)
        events.append(Announcement("old", "OLD", at=0.0))
        session.on_timeout()
        self.assertFalse(
            any("ANNOUNCE 950 <- 950" in line for line in log)
        )

    def test_a_source_that_failed_first_seeds_on_its_first_success(self):
        calls = []

        def provider(ctx):
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return (Announcement("old", "OLD", at=0.0),)

        session, clock, log = self.make_session(provider)
        session.on_timeout()
        clock.advance(5.0)
        session.on_timeout()
        self.assertTrue(any("ERROR RuntimeError" in line for line in log))
        self.assertFalse(
            any("ANNOUNCE 950 <- 950: 1 new" in line for line in log)
        )

    def test_provider_errors_log_the_caller_and_do_not_close_the_session(self):
        def provider(ctx):
            raise RuntimeError("boom")

        session, _, log = self.make_session(provider)
        session.on_timeout()
        self.assertTrue(
            any(
                "ANNOUNCE 950 <- 950 ERROR RuntimeError: boom" in line
                for line in log
            )
        )

    def test_disabled_policy_does_not_poll_or_log(self):
        def provider(ctx):
            return (Announcement("k", "TEXT"),)

        session, _, log = self.make_session(
            provider, policy=AnnouncementPolicy(enabled=False)
        )
        self.assertIsNone(session.next_timeout())
        session.on_timeout()
        self.assertEqual(log, [])


class PageSourceIntegrationTests(unittest.TestCase):
    def test_sports_page_declares_the_goal_source(self):
        import pages

        page = pages.build_registry().get("150")
        self.assertIs(page.announce, collect_goal_alerts)
        self.assertEqual(page.announce_channel, SPORTS_CHANNEL)

    def test_diagnostics_page_declares_the_test_source(self):
        from diagnostics_pages.announce import announce

        self.assertIs(announce.announce, _announce)
        self.assertEqual(announce.announce_channel, "diagnostics")


if __name__ == "__main__":
    unittest.main()
