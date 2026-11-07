import unittest
from unittest.mock import Mock

import pages

from minitel import Registry, Screen, page
from pages.home import MENU_LIMIT, menu_entries, welcome


def make_ctx(registry):
    ctx = Mock()
    ctx.registry = registry
    return ctx


class HomeMenuTests(unittest.TestCase):
    def test_public_menu_is_aliases_in_numeric_order(self):
        entries, extra = menu_entries(pages.build_registry())
        self.assertEqual(extra, 0)
        self.assertEqual(
            [(alias, entry.number) for _, alias, entry in entries],
            [
                ("1", "110"),
                ("2", "120"),
                ("3", "130"),
                ("4", "140"),
                ("5", "150"),
                ("6", "155"),
                ("7", "190"),
            ],
        )

    def test_home_renders_the_public_menu(self):
        text = welcome.render(make_ctx(pages.build_registry())).to_text()
        lines = text.splitlines()
        self.assertEqual(lines[5].strip(), "1  NEWS")
        self.assertEqual(lines[6].strip(), "2  WEATHER")
        self.assertEqual(lines[7].strip(), "3  ABOUT")
        self.assertEqual(lines[8].strip(), "4  GUESTBOOK")
        self.assertEqual(lines[9].strip(), "5  LIVE SCORES")
        self.assertEqual(lines[10].strip(), "6  VIDIPRINTER")
        self.assertEqual(lines[11].strip(), "7  SCREENSAVER")
        self.assertEqual(lines[12].strip(), "TYPE A NUMBER, THEN ENVOI:")

    def test_menu_skips_home_non_numeric_and_zero_aliases(self):
        registry = Registry()

        @page("100", title="HOME", aliases=("",))
        def home(ctx):
            return Screen()

        @page("800", title="MULTI", aliases=("9", "6"))
        def multi(ctx):
            return Screen()

        @page("801", title="WORD", aliases=("NEWS",))
        def word(ctx):
            return Screen()

        @page("802", title="ZERO", aliases=("0",))
        def zero(ctx):
            return Screen()

        registry.add(home)
        registry.add(multi)
        registry.add(word)
        registry.add(zero)

        entries, extra = menu_entries(registry)
        self.assertEqual(extra, 0)
        self.assertEqual(
            [(alias, entry.number) for _, alias, entry in entries],
            [("6", "800")],
        )

    def test_menu_caps_at_the_lowest_aliases(self):
        registry = Registry()
        for index in range(1, MENU_LIMIT + 2):
            @page(
                str(800 + index),
                title=f"PAGE {index}",
                aliases=(str(index),),
            )
            def extra(ctx):
                return Screen()

            registry.add(extra)

        entries, extra = menu_entries(registry)
        self.assertEqual(len(entries), MENU_LIMIT)
        self.assertEqual(extra, 1)
        self.assertEqual(
            [alias for _, alias, _ in entries],
            [str(index) for index in range(1, MENU_LIMIT + 1)],
        )

    def test_extra_aliases_are_reported_in_the_hint(self):
        registry = Registry()
        for index in range(1, MENU_LIMIT + 2):
            @page(
                str(800 + index),
                title=f"PAGE {index}",
                aliases=(str(index),),
            )
            def extra(ctx):
                return Screen()

            registry.add(extra)

        text = welcome.render(make_ctx(registry)).to_text()
        self.assertIn("TYPE A NUMBER, THEN ENVOI  (+1 MORE)", text)

    def test_two_digit_alias_is_rendered(self):
        registry = Registry()

        @page("800", title="TEN", aliases=("10",))
        def ten(ctx):
            return Screen()

        registry.add(ten)

        lines = welcome.render(make_ctx(registry)).to_text().splitlines()
        self.assertTrue(any(line.startswith("10 TEN") for line in lines))


if __name__ == "__main__":
    unittest.main()
