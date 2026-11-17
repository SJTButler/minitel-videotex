import unittest

import pages

from minitel import Carousel, M1, Registry, Region, Screen, Session, page

SUITE = bytes([0x13, 0x48])
ENVOI = bytes([0x13, 0x41])


def make_session(initial, *page_objects):
    registry = Registry()
    for page_object in page_objects:
        registry.add(page_object)
    session = Session(
        registry,
        M1,
        initial=initial,
        fallback=registry.get(initial),
    )
    session.start()
    return session


@page("980")
def home(ctx):
    return Screen()


@page("981")
def pure_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(6, 4)
    screen.text(0, 0, pager.label)
    return screen


@page("982")
def pure_choice(ctx):
    screen = Screen()
    choice = ctx.set_choice(4, 2)
    screen.text(0, 0, f"SEL {choice.selected}")
    return screen


@page("983")
def pure_form(ctx):
    screen = Screen()
    ctx.add_field("query", 0, 0, 4)
    return screen


@page("984")
def composite_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(6, 4)
    ctx.add_field("query", 1, 0, 5)
    screen.text(0, 0, pager.label)
    return screen


@page("985")
def carousel_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(6, 4, carousel=Carousel(hold=10.0))
    screen.text(0, 0, pager.label)
    return screen


@page("987", on_submit=lambda ctx, line: "980" if line.strip() == "GO" else None)
def ambient_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(6, 4)
    ctx.set_input(1, 0, 5)
    screen.text(0, 0, pager.label)
    return screen


@page("988")
def ambient_only(ctx):
    screen = Screen()
    ctx.set_input(0, 0, 4)
    return screen


@page("989")
def mixed_inputs(ctx):
    screen = Screen()
    ctx.set_input(0, 0, 4)
    ctx.add_field("query", 1, 0, 4)
    return screen


@page("990", regions=(Region("items", kind="choice", page_size=2),))
def ambient_commands(ctx):
    screen = Screen()
    ctx.set_input(0, 0, 4)
    ctx.set_choice(
        ("A", "B"),
        region="items",
        commands={"*": lambda item: None},
    )
    return screen


@page("986", regions=(Region("rows", kind="pager", page_size=2),))
def named_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(4, region="rows")
    screen.text(0, 0, pager.label)
    return screen


class PurePaneTests(unittest.TestCase):
    def test_pure_pager_is_the_main_region(self):
        session = make_session("981", home, pure_pager)
        self.assertEqual(
            session.regions["main"].definition.kind, "pager"
        )
        self.assertIs(session.pager, session.regions["main"].cursor)

        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 2)
        self.assertIs(session.pager, session.regions["main"].cursor)

    def test_pure_pager_offset_survives_navigation(self):
        session = make_session("981", home, pure_pager)
        session.feed(SUITE)
        session.navigate("980")
        session.navigate("981")
        self.assertEqual(session.pager.page_number, 2)

    def test_pure_choice_is_the_main_region(self):
        session = make_session("982", home, pure_choice)
        self.assertEqual(
            session.regions["main"].definition.kind, "choice"
        )
        self.assertIs(session.choice, session.regions["main"].cursor)

        session.feed(SUITE)
        self.assertEqual(session.choice.selected, 1)
        self.assertIs(session.choice, session.regions["main"].cursor)

    def test_pure_form_is_the_main_region(self):
        session = make_session("983", home, pure_form)
        self.assertEqual(
            session.regions["main"].definition.kind, "form"
        )
        session.feed(b"AB")
        self.assertEqual(session.values["query"], "AB")
        self.assertTrue(
            session.screen.to_text().splitlines()[0].startswith("AB")
        )

    def test_pager_with_a_carousel_is_the_main_region(self):
        session = make_session("985", home, carousel_pager)
        self.assertEqual(tuple(session.regions), ("main",))
        self.assertEqual(
            session.regions["main"].definition.kind, "pager"
        )
        self.assertIs(session.pager, session.regions["main"].cursor)
        self.assertIs(session.pagers["985"], session.pager)

    def test_ambient_pager_is_the_main_region(self):
        session = make_session("987", home, ambient_pager)
        self.assertEqual(
            session.regions["main"].definition.kind, "pager"
        )
        session.feed(b"2")
        self.assertEqual(session.line, "2")
        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 2)
        self.assertEqual(session.line, "")

    def test_ambient_text_wins_envoi_over_the_pager(self):
        session = make_session("987", home, ambient_pager)
        session.feed(b"GO")
        session.feed(ENVOI)
        self.assertEqual(session.current.number, "980")
        self.assertEqual(session.line, "")

    def test_ambient_only_page_has_no_region(self):
        session = make_session("988", home, ambient_only)
        self.assertEqual(session.regions, {})
        session.feed(b"AB")
        self.assertEqual(session.line, "AB")

    def test_field_plus_pager_is_rejected(self):
        with self.assertRaises(ValueError):
            make_session("984", home, composite_pager)

    def test_mixing_ambient_and_form_fields_is_rejected(self):
        with self.assertRaises(ValueError):
            make_session("989", home, mixed_inputs)

    def test_mixing_ambient_and_commands_is_rejected(self):
        with self.assertRaises(ValueError):
            make_session("990", home, ambient_commands)

    def test_named_regions_keep_the_region_store(self):
        session = make_session("986", home, named_pager)
        self.assertEqual(tuple(session.regions), ("rows",))
        self.assertIsNotNone(session.regions["rows"].cursor)
        self.assertIsNone(session.pager)


class PublicPageShapeTests(unittest.TestCase):
    def test_directory_page_is_a_main_pager(self):
        registry = pages.build_registry()
        session = Session(
            registry,
            M1,
            initial="199",
            fallback=registry.get(pages.NOT_FOUND),
        )
        session.start()
        self.assertEqual(tuple(session.regions), ("main",))
        self.assertEqual(
            session.regions["main"].definition.kind, "pager"
        )
        self.assertIsNotNone(session.pager)

    def test_notes_page_uses_named_regions(self):
        registry = pages.build_registry()
        session = Session(
            registry,
            M1,
            initial="180",
            fallback=registry.get(pages.NOT_FOUND),
        )
        session.start()
        self.assertEqual(tuple(session.regions), ("items", "entry"))


if __name__ == "__main__":
    unittest.main()
