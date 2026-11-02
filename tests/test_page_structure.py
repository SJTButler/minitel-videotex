import unittest
from pathlib import Path

PAGES = Path(__file__).resolve().parents[1] / "pages"


def source_files(path):
    return sorted(
        path.glob("*.py"),
        key=lambda item: item.name,
    )


class PageStructureTests(unittest.TestCase):
    def test_feature_top_level_contains_pages(self):
        for feature in PAGES.iterdir():
            if not feature.is_dir() or feature.name in {"common", "__pycache__"}:
                continue
            for path in source_files(feature):
                if path.name == "__init__.py":
                    continue
                self.assertIn(
                    "@page(",
                    path.read_text(encoding="utf-8"),
                    f"{path} is a top-level feature module without a page",
                )

    def test_support_modules_contain_no_pages(self):
        for support in PAGES.glob("*/_support"):
            for path in source_files(support):
                self.assertNotIn(
                    "@page(",
                    path.read_text(encoding="utf-8"),
                    f"{path} defines a page outside a page module",
                )

    def test_root_page_modules_contain_pages(self):
        for path in source_files(PAGES):
            if path.name == "__init__.py":
                continue
            self.assertIn(
                "@page(",
                path.read_text(encoding="utf-8"),
                f"{path} is a top-level module without a page",
            )

    def test_layout_shim_is_gone(self):
        self.assertFalse((PAGES / "layout.py").exists())


if __name__ == "__main__":
    unittest.main()
