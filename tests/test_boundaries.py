import ast
import unittest
from pathlib import Path

import pages
from pages.news.directory import NEWS_SERVICES

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "pages" / "common"
DESIGN = ROOT / "minitel" / "design"
MINITEL = ROOT / "minitel"

TIMER_MODULES = {"asyncio", "sched", "threading"}


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                yield node.module


class LibraryBoundaryTests(unittest.TestCase):
    def test_minitel_does_not_import_the_application(self):
        for path in sorted(MINITEL.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for module in imported_modules(path):
                self.assertFalse(
                    module == "pages" or module.startswith("pages."),
                    f"{path} imports {module}",
                )
                self.assertFalse(
                    module == "services" or module.startswith("services."),
                    f"{path} imports {module}",
                )

    def test_pages_common_is_presentation_only(self):
        for path in sorted(COMMON.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("@page(", source, f"{path} defines a page")
            self.assertNotIn("ctx.session", source, f"{path} reaches the session")

            for module in imported_modules(path):
                self.assertFalse(
                    module == "services" or module.startswith("services."),
                    f"{path} imports {module}",
                )
                self.assertFalse(
                    module == "pages" or (
                        module.startswith("pages.")
                        and module != "pages.common"
                        and not module.startswith("pages.common.")
                    ),
                    f"{path} imports {module}",
                )
                self.assertFalse(
                    module in {"minitel.pagemodel", "minitel.session"},
                    f"{path} imports {module}",
                )
                self.assertNotIn(
                    module, TIMER_MODULES, f"{path} imports {module}"
                )


class DesignBoundaryTests(unittest.TestCase):
    def test_design_imports_are_stdlib_only(self):
        for path in sorted(DESIGN.glob("*.py")):
            for module in imported_modules(path):
                self.assertFalse(
                    module.startswith(("minitel", "pages", "services")),
                    f"{path} imports {module}",
                )


class ServiceDeclarationTests(unittest.TestCase):
    def test_news_directory_declares_every_service_in_its_table(self):
        page = pages.build_registry().get("110")
        for entry in NEWS_SERVICES:
            self.assertIn(entry.service, page.requires)


if __name__ == "__main__":
    unittest.main()
