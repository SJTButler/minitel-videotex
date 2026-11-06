import sys
import tempfile
import unittest
from pathlib import Path

import pages
import services

from pages.home import menu_entries
from run_server import load_registries, override_report


PAGE_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('801', title='EXTRA', aliases=('8',))\n"
    "def extra(ctx):\n"
    "    return Screen()\n"
)

ABOUT_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('130', title='EXTRA ABOUT', aliases=('3',))\n"
    "def about(ctx):\n"
    "    return Screen()\n"
)

ABOUT_NO_ALIAS_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('130', title='EXTRA ABOUT')\n"
    "def about(ctx):\n"
    "    return Screen()\n"
)

ALIAS_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('801', title='EXTRA SCORES', aliases=('4',))\n"
    "def scores(ctx):\n"
    "    return Screen()\n"
)

ALIAS_SECOND_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('802', title='SECOND SCORES', aliases=('4',))\n"
    "def scores(ctx):\n"
    "    return Screen()\n"
)


def write_package(directory, name, modules):
    package = Path(directory) / name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for module_name, source in modules.items():
        (package / f"{module_name}.py").write_text(
            source, encoding="utf-8"
        )
    return package


class ExtraPackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        while self.directory.name in sys.path:
            sys.path.remove(self.directory.name)
        for name in tuple(sys.modules):
            if name.startswith("extra_"):
                sys.modules.pop(name, None)

    def _add_path(self):
        sys.path.insert(0, self.directory.name)

    def test_extra_pages_compose_with_public_pages(self):
        write_package(
            self.directory.name, "extra_pages", {"page": PAGE_SOURCE}
        )
        self._add_path()

        registry = pages.build_registry("extra_pages")
        self.assertIsNotNone(registry.get("801"))
        self.assertIsNotNone(registry.get("8"))
        self.assertIsNotNone(registry.get("100"))
        self.assertIsNone(pages.build_registry().get("801"))

    def test_extra_page_alias_reaches_the_home_menu(self):
        write_package(
            self.directory.name, "extra_pages", {"page": PAGE_SOURCE}
        )
        self._add_path()

        entries, extra = menu_entries(pages.build_registry("extra_pages"))
        self.assertEqual(extra, 0)
        self.assertIn(
            ("8", "801"),
            [(alias, entry.number) for _, alias, entry in entries],
        )

    def test_page_number_override_replaces_page(self):
        write_package(
            self.directory.name,
            "extra_about_pages",
            {"page": ABOUT_SOURCE},
        )
        self._add_path()

        registry = pages.build_registry("extra_about_pages")
        self.assertEqual(registry.get("130").title, "EXTRA ABOUT")
        self.assertEqual(registry.get("3").title, "EXTRA ABOUT")
        self.assertNotIn(
            "ABOUT", [page.title for page in registry.all()]
        )

        self.assertEqual(len(registry.overrides), 1)
        event = registry.overrides[0]
        self.assertEqual(event.kind, "page")
        self.assertEqual(event.key, "130")
        self.assertEqual(event.old_page.title, "ABOUT")
        self.assertEqual(event.new_page.title, "EXTRA ABOUT")

        aliases = [
            (alias, entry.title)
            for _, alias, entry in menu_entries(registry)[0]
            if alias == "3"
        ]
        self.assertEqual(aliases, [("3", "EXTRA ABOUT")])

        report = override_report(registry)
        self.assertIn(
            "page 130: pages/130 -> extra_about_pages/130", report
        )
        self.assertIn("aliases moved: 3", report)

    def test_alias_override_keeps_the_public_page(self):
        write_package(
            self.directory.name,
            "extra_alias_pages",
            {"page": ALIAS_SOURCE},
        )
        self._add_path()

        registry = pages.build_registry("extra_alias_pages")
        self.assertEqual(registry.get("4").number, "801")
        self.assertEqual(registry.get("801").number, "801")
        self.assertEqual(registry.get("140").number, "140")
        self.assertNotIn(
            "4", registry.aliases_for(registry.get("140"))
        )
        self.assertIn("4", registry.aliases_for(registry.get("801")))

        aliases = [
            (alias, entry.title)
            for _, alias, entry in menu_entries(registry)[0]
            if alias == "4"
        ]
        self.assertEqual(aliases, [("4", "EXTRA SCORES")])

        self.assertEqual(len(registry.overrides), 1)
        event = registry.overrides[0]
        self.assertEqual(event.kind, "alias")
        self.assertEqual(event.key, "4")
        self.assertEqual(event.old_page.number, "140")
        self.assertEqual(event.new_page.number, "801")

        report = override_report(registry)
        self.assertIn(
            "alias 4: pages/140 -> extra_alias_pages/801", report
        )

    def test_three_layers_last_package_wins(self):
        write_package(
            self.directory.name,
            "extra_dev_pages",
            {"page": ALIAS_SOURCE},
        )
        write_package(
            self.directory.name,
            "extra_my_pages",
            {"page": ALIAS_SECOND_SOURCE},
        )
        self._add_path()

        registry = pages.build_registry(
            "extra_dev_pages", "extra_my_pages"
        )
        self.assertEqual(registry.get("4").number, "802")
        self.assertEqual(registry.get("801").number, "801")
        self.assertEqual(registry.get("802").number, "802")
        self.assertEqual(registry.get("140").number, "140")
        self.assertEqual(
            [event.key for event in registry.overrides],
            ["4", "4"],
        )
        aliases = [
            (alias, entry.title)
            for _, alias, entry in menu_entries(registry)[0]
            if alias == "4"
        ]
        self.assertEqual(aliases, [("4", "SECOND SCORES")])

    def test_page_override_can_remove_unclaimed_aliases(self):
        write_package(
            self.directory.name,
            "extra_about_no_alias",
            {"page": ABOUT_NO_ALIAS_SOURCE},
        )
        self._add_path()

        registry = pages.build_registry("extra_about_no_alias")
        self.assertEqual(registry.get("130").title, "EXTRA ABOUT")
        self.assertIsNone(registry.get("3"))
        self.assertNotIn(
            "3",
            [
                alias
                for _, alias, _ in menu_entries(registry)[0]
            ],
        )
        event = registry.overrides[0]
        self.assertEqual(event.old_page.aliases, ("3",))
        self.assertIn("aliases removed: 3", override_report(registry))

    def test_same_package_duplicate_still_fails(self):
        write_package(
            self.directory.name,
            "extra_dupe_pages",
            {
                "page": (
                    "from minitel.pagemodel import page\n"
                    "from minitel.render import Screen\n"
                    "@page('130', title='ONE')\n"
                    "def one(ctx):\n"
                    "    return Screen()\n"
                    "@page('130', title='TWO')\n"
                    "def two(ctx):\n"
                    "    return Screen()\n"
                )
            },
        )
        self._add_path()

        with self.assertRaises(ValueError):
            pages.build_registry("extra_dupe_pages")

    def test_same_package_duplicate_alias_still_fails(self):
        write_package(
            self.directory.name,
            "extra_dupe_alias",
            {
                "page": (
                    "from minitel.pagemodel import page\n"
                    "from minitel.render import Screen\n"
                    "@page('801', title='ONE', aliases=('5',))\n"
                    "def one(ctx):\n"
                    "    return Screen()\n"
                    "@page('802', title='TWO', aliases=('5',))\n"
                    "def two(ctx):\n"
                    "    return Screen()\n"
                )
            },
        )
        self._add_path()

        with self.assertRaises(ValueError):
            pages.build_registry("extra_dupe_alias")

    def test_extra_services_compose_with_public_services(self):
        write_package(
            self.directory.name,
            "extra_services",
            {
                "service": (
                    "from minitel.data.services import service\n"
                    "@service('extra_demo')\n"
                    "def build_extra():\n"
                    "    return object()\n"
                )
            },
        )
        self._add_path()

        registry = services.build_registry("extra_services")
        self.assertIn("extra_demo", registry)
        self.assertIn("sports", registry)
        self.assertNotIn("extra_demo", services.build_registry())

    def test_duplicate_service_key_fails(self):
        write_package(
            self.directory.name,
            "extra_dupe_services",
            {
                "service": (
                    "from minitel.data.services import service\n"
                    "@service('sports')\n"
                    "def build_dupe():\n"
                    "    return object()\n"
                )
            },
        )
        self._add_path()

        with self.assertRaises(ValueError):
            services.build_registry("extra_dupe_services")

    def test_load_registries_uses_extra_paths(self):
        write_package(
            self.directory.name, "extra_pages", {"page": PAGE_SOURCE}
        )
        write_package(
            self.directory.name,
            "extra_services",
            {
                "service": (
                    "from minitel.data.services import service\n"
                    "@service('extra_demo')\n"
                    "def build_extra():\n"
                    "    return object()\n"
                )
            },
        )

        page_registry, service_registry = load_registries(
            pages_packages=("extra_pages",),
            services_packages=("extra_services",),
            extra_paths=(self.directory.name,),
        )
        self.assertIsNotNone(page_registry.get("801"))
        self.assertIn("extra_demo", service_registry)

    def test_missing_extra_package_is_clear(self):
        with self.assertRaises(SystemExit) as caught:
            load_registries(pages_packages=("missing_extra_pages",))
        self.assertIn(
            "cannot load pages package", str(caught.exception)
        )


if __name__ == "__main__":
    unittest.main()
