import re
import unittest
from pathlib import Path

import pages

DOC = Path(__file__).resolve().parents[1] / "docs" / "authoring-pages.md"
START = "<!-- page-catalogue:start -->"
END = "<!-- page-catalogue:end -->"
ALIAS = re.compile(r"\((\d+)\)")
EXTENSION = re.compile(r"(\d+)#([A-Z]+)")


def catalogue_rows():
    text = DOC.read_text(encoding="utf-8")
    body = text.split(START, 1)[1].split(END, 1)[0]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].lower() == "number":
            continue
        if set(cells[0]) <= {"-", ":", " "}:
            continue
        rows.append((cells[0], cells[1]))
    return rows


def expand(number_cell):
    value = number_cell.replace("`", "").strip()
    match = re.fullmatch(r"(\d+)-(\d+)", value)
    if match:
        low, high = (int(part) for part in match.groups())
        return [str(number) for number in range(low, high + 1)]
    return [value]


class PageCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = pages.build_registry()

    def test_catalogue_markers_are_present(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn(START, text)
        self.assertIn(END, text)

    def test_every_documented_page_is_registered(self):
        for number_cell, _ in catalogue_rows():
            for number in expand(number_cell):
                with self.subTest(number=number):
                    self.assertIsNotNone(
                        self.registry.get(number),
                        f"documented page {number!r} is not registered",
                    )

    def test_every_public_numeric_page_is_documented(self):
        documented = set()
        for number_cell, _ in catalogue_rows():
            documented.update(expand(number_cell))
        documented = {number for number in documented if number.isdigit()}

        public = {
            page.number
            for page in self.registry.all()
            if page.number.isdigit()
            and (
                100 <= int(page.number) <= 199
                or 900 <= int(page.number) <= 912
            )
        }
        self.assertEqual(
            sorted(public - documented),
            [],
            "public pages missing from docs/authoring-pages.md",
        )
        self.assertEqual(
            sorted(documented - public),
            [],
            "documented page numbers with no public page",
        )

    def test_documented_aliases_resolve_to_the_same_page(self):
        for number_cell, description in catalogue_rows():
            for number in expand(number_cell):
                page = self.registry.get(number)
                if page is None:
                    continue
                for alias in ALIAS.findall(description):
                    with self.subTest(number=number, alias=alias):
                        self.assertIs(self.registry.get(alias), page)

    def test_documented_extension_bases_declare_extensions(self):
        for number_cell, description in catalogue_rows():
            for base, token in EXTENSION.findall(description):
                with self.subTest(number=number_cell, route=f"{base}#{token}"):
                    page = self.registry.get(base)
                    self.assertIsNotNone(page)
                    self.assertTrue(
                        page.extensions,
                        f"documented route {base}#{token} needs "
                        f"extensions=True on page {base}",
                    )


if __name__ == "__main__":
    unittest.main()
