import unittest

from minitel.pagemodel import Registry, page
from minitel.render import Screen


@page("900", screensaver="group")
def late(ctx):
    return Screen()


@page("800", screensaver="group")
def early(ctx):
    return Screen()


class RegistryTests(unittest.TestCase):
    def test_adding_the_same_page_twice_is_idempotent(self):
        registry = Registry()
        registry.add(late)
        registry.add(late)

        self.assertEqual(registry.all(), (late,))
        self.assertIs(registry.get("900"), late)

    def test_two_distinct_pages_cannot_share_a_key(self):
        @page("900")
        def other(ctx):
            return Screen()

        registry = Registry()
        registry.add(late)
        with self.assertRaises(ValueError):
            registry.add(other)

    def test_screensaver_group_pages_are_in_page_number_order(self):
        registry = Registry()
        registry.add(late)
        registry.add(early)

        self.assertEqual(
            [page.number for page in registry.screensaver_groups()["group"]],
            ["800", "900"],
        )


if __name__ == "__main__":
    unittest.main()
