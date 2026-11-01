import sys
import tempfile
import unittest
from pathlib import Path

import services
from minitel.services import ServiceRegistry


class DiscoveryTests(unittest.TestCase):
    def test_discovers_all_services_in_key_order(self):
        registry = services.build_registry()
        self.assertIsInstance(registry, ServiceRegistry)
        self.assertEqual(
            list(registry),
            ["hackernews", "sports", "weather"],
        )

    def test_services_expose_their_read_apis(self):
        registry = services.build_registry()
        self.assertTrue(hasattr(registry["hackernews"], "front_page"))
        self.assertTrue(hasattr(registry["weather"], "weather"))
        self.assertTrue(hasattr(registry["sports"], "snapshot"))

    def test_discovery_is_repeatable(self):
        first = services.build_registry()
        second = services.build_registry()
        self.assertEqual(list(first), list(second))
        self.assertIsNot(first["sports"], second["sports"])

    def test_duplicate_keys_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "dupe_services"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            for name in ("one", "two"):
                (package / f"{name}.py").write_text(
                    "from minitel.services import service\n"
                    "@service('same')\n"
                    f"def build_{name}():\n"
                    "    return object()\n",
                    encoding="utf-8",
                )
            sys.path.insert(0, directory)
            try:
                with self.assertRaises(ValueError):
                    ServiceRegistry().discover("dupe_services")
            finally:
                sys.path.remove(directory)
                for name in tuple(sys.modules):
                    if name == "dupe_services" or name.startswith(
                        "dupe_services."
                    ):
                        sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
