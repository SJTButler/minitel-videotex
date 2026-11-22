import unittest

from minitel import M1, Screen, page
from minitel.pagemodel import Registry
from minitel.session import Session

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SOMMAIRE = bytes([0x13, 0x46])


def state_page(number, *, retain=False, fail=False, **options):
    def render(ctx):
        if fail:
            raise RuntimeError(f"render failed on {number}")
        screen = Screen()
        screen.text(0, 0, f"PAGE {number}")
        ctx.set_input(20, 6, 10)
        return screen

    def submit(ctx, line):
        ctx.page_state["value"] = line
        ctx.clear_input()
        return ctx.page.number

    return page(
        number,
        title=f"PAGE {number}",
        retain_state=retain,
        on_submit=submit,
        **options,
    )(render)


def tick_page(number):
    def render(ctx):
        screen = Screen()
        screen.text(0, 0, f"PAGE {number}")
        ctx.set_input(20, 6, 10)
        return screen

    def submit(ctx, line):
        ctx.page_state["value"] = line
        ctx.clear_input()
        return number

    def tick(ctx):
        ctx.page_state["ticks"] = ctx.page_state.get("ticks", 0) + 1
        return None

    return page(
        number,
        title=f"PAGE {number}",
        on_submit=submit,
        on_tick=tick,
        tick_interval=1.0,
    )(render)


def resource_page(number, resource, *, scope="page", fail_render=False):
    def render(ctx):
        ctx.add_resource(resource, scope=scope)
        if fail_render:
            raise RuntimeError(f"render failed on {number}")
        return Screen()

    return page(number, title=f"PAGE {number}")(render)


def two_resource_page(number, page_resource, connection_resource):
    def render(ctx):
        ctx.add_resource(page_resource, scope="page")
        ctx.add_resource(connection_resource)
        return Screen()

    return page(number, title=f"PAGE {number}")(render)


class Recorder:
    def __init__(self, name, events, *, fail=False):
        self.name = name
        self.events = events
        self.fail = fail
        self.closed = 0

    def close(self):
        self.closed += 1
        self.events.append(self.name)
        if self.fail:
            raise RuntimeError(self.name)


def make_session(*pages, initial="700", log=None):
    registry = Registry()
    for item in pages:
        registry.add(item)
    session = Session(registry, M1, initial=initial, log=log)
    session.start()
    return session


def value(session, page_key):
    return session._page_state.get(page_key, {}).get("value")


class PageStateTests(unittest.TestCase):
    def test_state_is_isolated_per_page_key(self):
        session = make_session(
            state_page("700", retain=True),
            state_page("701", retain=True),
            initial="700",
        )

        session.feed(b"one" + ENVOI)
        session.navigate("701")
        session.feed(b"two" + ENVOI)

        self.assertEqual(value(session, "700"), "one")
        self.assertEqual(value(session, "701"), "two")

    def test_state_is_discarded_on_leave_by_default(self):
        session = make_session(
            state_page("702"),
            state_page("703"),
            initial="702",
        )

        session.feed(b"gone" + ENVOI)
        self.assertEqual(value(session, "702"), "gone")

        session.navigate("703")
        self.assertNotIn("702", session._page_state)

    def test_retained_state_survives_child_navigation_and_retour(self):
        session = make_session(
            state_page("704", retain=True),
            state_page("705"),
            initial="704",
        )

        session.feed(b"kept" + ENVOI)
        session.navigate("705")
        self.assertEqual(value(session, "704"), "kept")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "704")
        self.assertEqual(value(session, "704"), "kept")

    def test_retained_state_is_pruned_when_the_route_leaves_history(self):
        session = make_session(
            state_page("710"),
            state_page("711", retain=True, back_page="713"),
            state_page("713"),
            initial="710",
        )

        session.navigate("711")
        session.feed(b"stale" + ENVOI)
        self.assertEqual(value(session, "711"), "stale")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "713")
        self.assertNotIn("711", session._page_state)

    def test_sommaire_clears_all_retained_state(self):
        session = make_session(
            state_page("706", retain=True),
            state_page("707"),
            initial="706",
        )

        session.feed(b"visit" + ENVOI)
        session.navigate("707")
        self.assertIn("706", session._page_state)

        session.feed(SOMMAIRE)
        self.assertEqual(session.current.number, "706")
        self.assertEqual(session._page_state, {})

    def test_direct_entry_after_sommaire_starts_fresh(self):
        session = make_session(
            state_page("708", retain=True),
            state_page("709"),
            initial="708",
        )

        session.feed(b"old" + ENVOI)
        session.navigate("709")
        session.feed(SOMMAIRE)

        session.navigate("708")
        self.assertNotIn("value", session._page_state.get("708", {}))

    def test_extension_route_has_its_own_state(self):
        session = make_session(
            state_page("714", retain=True, extensions=True),
            initial="714",
        )

        session.feed(b"base" + ENVOI)
        session.navigate("714#A")
        session.feed(b"ext" + ENVOI)

        self.assertEqual(value(session, "714"), "base")
        self.assertEqual(value(session, "714#A"), "ext")
        self.assertTrue(session.registry.get("714#A").retain_state)

    def test_faulting_page_state_is_cleared_and_other_pages_survive(self):
        session = make_session(
            state_page("716", retain=True),
            state_page("715", fail=True, back_page="716"),
            initial="716",
        )

        session.feed(b"healthy" + ENVOI)
        session.navigate("715")

        self.assertEqual(session.page_error, "render")
        self.assertNotIn("715", session._page_state)
        self.assertEqual(value(session, "716"), "healthy")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "716")
        self.assertEqual(value(session, "716"), "healthy")

    def test_page_state_survives_ticks_and_submits_while_current(self):
        session = make_session(tick_page("722"), initial="722")

        session.feed(b"first" + ENVOI)
        session.tick()
        session.feed(b"second" + ENVOI)

        state = session._page_state["722"]
        self.assertEqual(state["value"], "second")
        self.assertEqual(state["ticks"], 1)


class PageResourceTests(unittest.TestCase):
    def test_page_resource_closes_on_leave_and_not_again_on_close(self):
        events = []
        record = Recorder("page-717", events)
        session = make_session(
            resource_page("717", record),
            state_page("718"),
            initial="717",
        )

        session.navigate("718")
        self.assertEqual(events, ["page-717"])
        self.assertEqual(record.closed, 1)

        session.close()
        self.assertEqual(record.closed, 1)

    def test_connection_resource_survives_page_leave(self):
        events = []
        record = Recorder("connection-719", events)
        session = make_session(
            resource_page("719", record, scope="connection"),
            state_page("720"),
            initial="719",
        )

        session.navigate("720")
        self.assertEqual(events, [])

        session.close()
        self.assertEqual(events, ["connection-719"])

    def test_page_and_connection_resources_close_in_reverse_order(self):
        events = []
        page_resource = Recorder("page-721", events)
        connection_resource = Recorder("connection-721", events)
        session = make_session(
            two_resource_page("721", page_resource, connection_resource),
            initial="721",
        )

        session.close()
        self.assertEqual(
            events, ["connection-721", "page-721"]
        )

    def test_page_resource_closes_on_the_error_boundary(self):
        events = []
        record = Recorder("page-723", events)
        session = make_session(
            resource_page("723", record, fail_render=True),
            initial="723",
        )

        self.assertEqual(session.page_error, "render")
        self.assertEqual(events, ["page-723"])
        self.assertEqual(record.closed, 1)

    def test_page_resource_close_error_does_not_block_navigation(self):
        events = []
        logs = []
        record = Recorder("page-724", events, fail=True)
        session = make_session(
            resource_page("724", record),
            state_page("725"),
            initial="724",
            log=logs.append,
        )

        session.navigate("725")

        self.assertEqual(session.current.number, "725")
        self.assertEqual(events, ["page-724"])
        self.assertTrue(
            any("page resource close error" in message for message in logs)
        )


if __name__ == "__main__":
    unittest.main()
