import unittest

import minitel
import minitel.data
import minitel.design
import minitel.pagemodel
import minitel.protocol
import minitel.render
import minitel.session
import minitel.terminal


class PackageLayoutTests(unittest.TestCase):
    def test_public_surface_uses_the_new_packages(self):
        self.assertIs(minitel.Pager, minitel.design.Pager)
        self.assertIs(minitel.Carousel, minitel.design.Carousel)
        self.assertIs(minitel.InputField, minitel.design.InputField)
        self.assertIs(minitel.Page, minitel.pagemodel.Page)
        self.assertIs(minitel.Session, minitel.session.Session)
        self.assertIs(minitel.Screensaver, minitel.session.Screensaver)
        self.assertIs(minitel.Screen, minitel.render.Screen)
        self.assertIs(minitel.M1, minitel.terminal.profiles.M1)

    def test_old_flat_modules_are_gone(self):
        for module in (
            "cache",
            "carousel",
            "codec",
            "http",
            "pages",
            "paging",
            "power",
            "profiles",
            "screen",
            "screensaver",
            "services",
        ):
            with self.assertRaises(ModuleNotFoundError):
                __import__(f"minitel.{module}")


if __name__ == "__main__":
    unittest.main()
