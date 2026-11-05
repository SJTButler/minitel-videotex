import sys
import tempfile
import unittest
from pathlib import Path

import pages
import services

from pages.home import menu_entries
from run_server import load_registries


PAGE_SOURCE = (
    "from minitel.pagemodel import page\n"
    "from minitel.render import Screen\n"
    "@page('801', title='EXTRA', aliases=('8',))\n"
    "def extra(ctx):\n"
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

    def test_duplicate_page_key_fails(self):
        write_package(
            self.directory.name,
            "extra_dupe_pages",
            {
                "page": (
                    "from minitel.pagemodel import page\n"
                    "from minitel.render import Screen\n"
                    "@page('100', title='DUPE')\n"
                    "def dupe(ctx):\n"
                    "    return Screen()\n"
                )
            },
        )
        self._add_path()

        with self.assertRaises(ValueError):
            pages.build_registry("extra_dupe_pages")

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
