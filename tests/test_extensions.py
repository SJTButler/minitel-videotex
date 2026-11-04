import unittest

from minitel.pagemodel import ExtensionPage, Registry, page, split_extension
from minitel.render import Screen
from minitel.session import Session
from minitel.terminal import profiles
from minitel.terminal.power import POWER_OFF, POWER_ON

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
GUIDE = bytes([0x13, 0x44])
SOMMAIRE = bytes([0x13, 0x46])


@page("650", title="EXT", extensions=True, tick_interval=1.0,
      on_submit=lambda ctx, line: _submit(ctx, line),
      on_key=lambda ctx, key: _key(ctx, key),
      on_tick=lambda ctx: _tick(ctx))
def ext(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "INDEX")
    s.text(1, 0, ctx.page.number)
    ctx.set_input(20, 6, 10)
    return s


def _submit(ctx, line):
    ctx.state["submit_extension"] = ctx.extension
    if line == "STAY":
        return ctx.page.number
    return None


def _key(ctx, key):
    ctx.state["key_extension"] = ctx.extension
    return None


def _tick(ctx):
    ctx.state["tick_extension"] = ctx.extension
    return None


@page("651", title="PLAIN")
def plain(ctx):
    s = Screen()
    s.text(0, 0, "PLAIN")
    return s


@page("640", title="PARENT")
def parent(ctx):
    s = Screen()
    s.text(0, 0, "PARENT")
    ctx.set_input(20, 6, 10)
    return s


@page("652", title="TRANSIENT", transient=True, extensions=True)
def transient(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "TINDEX")
    ctx.set_input(20, 6, 10)
    return s


@page("660", title="ALIASED", aliases=("66",), extensions=True)
def aliased(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "AINDEX")
    return s


@page("680", title="BASE PARENT", extensions=True,
      extension_back_page="640")
def base_parent(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "BPINDEX")
    ctx.set_input(20, 6, 10)
    return s


@page("681", title="OTHER PARENT", extensions=True,
      extension_back_page="660")
def other_parent(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "OPINDEX")
    ctx.set_input(20, 6, 10)
    return s


@page("690", title="EXT PARENT", extensions=True, back_page="640")
def ext_parent(ctx):
    s = Screen()
    s.text(0, 0, ctx.extension or "EPINDEX")
    ctx.set_input(20, 6, 10)
    return s


@page("691", title="DETAIL", back_page="690")
def detail(ctx):
    s = Screen()
    s.text(0, 0, "DETAIL")
    ctx.set_input(20, 6, 10)
    return s


@page("692", title="TAKER", extensions=True)
def taker(ctx):
    token = ctx.take_extension()
    ctx.state["taken"] = token
    s = Screen()
    s.text(0, 0, token or "NONE")
    ctx.set_input(20, 6, 10)
    return s


def make_registry():
    registry = Registry()
    registry.add(ext)
    registry.add(plain)
    registry.add(parent)
    registry.add(transient)
    registry.add(aliased)
    registry.add(base_parent)
    registry.add(other_parent)
    registry.add(ext_parent)
    registry.add(detail)
    registry.add(taker)
    return registry


class ExtensionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = make_registry()

    def test_extension_route_returns_an_extension_page(self):
        route = self.registry.get("650#1")

        self.assertIsInstance(route, ExtensionPage)
        self.assertIs(route.base, ext)
        self.assertEqual(route.extension, "1")
        self.assertEqual(route.number, "650#1")

    def test_declared_extension_parent_is_used_by_the_route(self):
        self.assertEqual(self.registry.get("680#1").back_page, "640")
        self.assertEqual(self.registry.get("681#1").back_page, "660")
        self.assertIsNone(self.registry.get("650#1").back_page)

    def test_base_page_is_unchanged(self):
        self.assertIs(self.registry.get("650"), ext)

    def test_page_must_opt_in(self):
        self.assertIsNone(self.registry.get("651#1"))

    def test_unknown_base_is_not_a_route(self):
        self.assertIsNone(self.registry.get("999#1"))

    def test_invalid_routes_are_rejected(self):
        for key in (
            "650#",
            "#1",
            "650#1#2",
            "650#1234567",
            "650#A-B",
            "650#A B",
            "650#é",
        ):
            with self.subTest(key=key):
                self.assertIsNone(self.registry.get(key))

    def test_token_is_uppercased(self):
        self.assertEqual(self.registry.get("650#abc").number, "650#ABC")

    def test_pound_glyph_works_as_the_separator(self):
        self.assertEqual(self.registry.get("650£1").number, "650#1")

    def test_alias_route_uses_the_canonical_base_number(self):
        route = self.registry.get("66#abc")

        self.assertEqual(route.number, "660#ABC")
        self.assertIs(route.base, aliased)

    def test_extension_routes_are_not_registered_pages(self):
        before = len(self.registry.all())
        self.registry.get("650#1")
        self.assertEqual(len(self.registry.all()), before)

    def test_registered_keys_cannot_contain_the_separator(self):
        with self.assertRaises(ValueError):
            Registry().add(page("650#1")(lambda ctx: Screen()))

        with self.assertRaises(ValueError):
            Registry().add(
                page("670", aliases=("67#1",))(lambda ctx: Screen())
            )

    def test_split_extension_normalises_and_validates(self):
        self.assertEqual(split_extension("650#1"), ("650", "1"))
        self.assertEqual(split_extension("650£abc"), ("650", "ABC"))
        self.assertIsNone(split_extension("650"))
        self.assertIsNone(split_extension("650#1#2"))
        self.assertIsNone(split_extension("650#1234567"))


class ExtensionDelegationTests(unittest.TestCase):
    def test_extension_page_delegates_base_metadata(self):
        def on_form(ctx, values):
            return None

        base = page(
            "670",
            title="FORM",
            aliases=("67",),
            back_page="640",
            extension_back_page="640",
            requires=("svc",),
            form=True,
            on_form=on_form,
            transient=True,
            tick_interval=2.0,
            no_screensaver=True,
            scroll=True,
            extensions=True,
        )(lambda ctx: Screen())
        route = ExtensionPage(base, "A")

        self.assertEqual(route.number, "670#A")
        self.assertEqual(route.title, "FORM")
        self.assertEqual(route.aliases, ())
        self.assertEqual(route.back_page, "640")
        self.assertEqual(route.extension_back_page, "640")
        self.assertEqual(route.requires, ("svc",))
        self.assertTrue(route.form)
        self.assertTrue(route.transient)
        self.assertEqual(route.tick_interval, 2.0)
        self.assertTrue(route.no_screensaver)
        self.assertTrue(route.scroll)
        self.assertIs(route.on_form, on_form)
        self.assertEqual(route.meta["extension"], "A")
        self.assertFalse(route.extensions)


class ExtensionSessionTests(unittest.TestCase):
    def setUp(self):
        self.registry = make_registry()
        self.session = Session(
            self.registry,
            profiles.M1,
            initial="640",
            fallback=self.registry.get("640"),
        )
        self.session.start()

    def test_direct_entry_renders_the_extension(self):
        self.session.navigate("650#1")

        self.assertEqual(self.session.current.number, "650#1")
        text = self.session.screen.to_text()
        self.assertIn("1", text.splitlines()[0])
        self.assertIn("650#1", text.splitlines()[1])

    def test_submit_routes_to_an_extension_key(self):
        self.session.navigate("650")
        self.session.feed(b"650#2" + ENVOI)

        self.assertEqual(self.session.current.number, "650#2")

    def test_retour_from_an_extension_follows_history(self):
        self.session.navigate("650#1")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "640")

    def test_retour_from_an_extension_entered_from_base_returns_to_base(self):
        self.session.navigate("650")
        self.session.navigate("650#1")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "650")

    def test_declared_extension_parent_is_used_for_direct_entry(self):
        self.session.navigate("681#1")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "660")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "640")

    def test_entering_from_the_declared_parent_pops_history(self):
        self.session.navigate("660")
        self.session.navigate("681#1")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "660")

    def test_declared_base_parent_is_used(self):
        self.session.navigate("680#1")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "640")

    def test_detail_retour_restores_the_extension_route(self):
        self.session.navigate("690#A")
        self.session.navigate("691")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "690#A")

    def test_take_extension_returns_once(self):
        self.session.navigate("692#A")
        self.assertEqual(self.session.state["taken"], "A")

        self.session.refresh()
        self.assertIsNone(self.session.state["taken"])

    def test_take_extension_is_not_reapplied_on_back(self):
        self.session.navigate("692#A")
        self.session.navigate("640")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "692#A")
        self.assertIsNone(self.session.state["taken"])

    def test_same_extension_route_does_not_duplicate_history(self):
        self.session.navigate("650#1")
        self.session.navigate("650#1")

        self.assertEqual(
            [page.number for page in self.session.history], ["640"]
        )

    def test_alias_route_canonicalises_the_page_number(self):
        self.session.navigate("66#1")

        self.assertEqual(self.session.current.number, "660#1")

    def test_invalid_route_falls_back_and_keeps_the_typed_key(self):
        self.session.navigate("650")
        self.session.feed(b"650##1" + ENVOI)

        self.assertEqual(self.session.current.number, "640")
        self.assertEqual(self.session.last_key, "650##1")

    def test_extension_is_available_to_submit_and_key_handlers(self):
        self.session.navigate("650#1")

        self.session.feed(b"STAY" + ENVOI)
        self.assertEqual(self.session.state["submit_extension"], "1")
        self.assertEqual(self.session.current.number, "650#1")

        self.session.feed(GUIDE)
        self.assertEqual(self.session.state["key_extension"], "1")

    def test_extension_is_available_to_ticks(self):
        self.session.navigate("650#1")
        self.session.tick()

        self.assertEqual(self.session.state["tick_extension"], "1")

    def test_retour_through_history_restores_the_extension_route(self):
        self.session.navigate("650#1")
        self.session.navigate("660")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "650#1")

    def test_sommaire_leaves_the_extension_route(self):
        self.session.navigate("650#1")
        self.session.feed(SOMMAIRE)

        self.assertEqual(self.session.current.number, "640")
        self.assertEqual(self.session.history, [])

    def test_power_cycle_preserves_the_extension_route(self):
        self.session.navigate("650#1")
        self.session.feed(POWER_OFF)
        self.session.feed(POWER_ON)

        self.assertEqual(self.session.current.number, "650#1")
        self.assertIn("1", self.session.screen.to_text().splitlines()[0])

    def test_transient_extension_is_not_pushed(self):
        self.session.navigate("652#1")
        self.session.navigate("640")

        self.assertEqual(self.session.history, [])
        self.assertEqual(self.session.current.number, "640")

    def test_non_extension_route_falls_back(self):
        self.session.navigate("651#1")

        self.assertEqual(self.session.current.number, "640")


if __name__ == "__main__":
    unittest.main()
