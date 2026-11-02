import unittest

import pages
import services

from minitel.pagemodel import FunctionPage, page
from minitel.render import Screen


class RequirementTests(unittest.TestCase):
    def test_full_graph_has_no_missing_services(self):
        page_registry = pages.build_registry()
        service_registry = services.build_registry()
        self.assertEqual(
            page_registry.missing_requirements(service_registry), {}
        )

    def test_page_declares_its_service(self):
        registry = pages.build_registry()
        self.assertEqual(registry.get("150").requires, ("sports",))
        self.assertEqual(registry.get("111").requires, ("hackernews",))
        self.assertEqual(registry.get("120").requires, ("weather",))
        self.assertEqual(registry.get("100").requires, ())

    def test_missing_service_reports_pages(self):
        registry = pages.build_registry()

        @page("999", title="MISSING", requires=("missing",))
        def missing(ctx):
            return Screen()

        registry.add(missing)
        self.assertEqual(
            registry.missing_requirements(services.build_registry()),
            {"missing": ("999",)},
        )

    def test_requires_must_be_a_sequence_of_keys(self):
        with self.assertRaises(TypeError):
            FunctionPage(
                "999", lambda ctx: Screen(), requires="sports"
            )
        with self.assertRaises(TypeError):
            FunctionPage(
                "999", lambda ctx: Screen(), requires=("",)
            )


if __name__ == "__main__":
    unittest.main()
