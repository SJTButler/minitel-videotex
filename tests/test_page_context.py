import unittest

from minitel.pagemodel import Registry, page
from minitel.terminal.profiles import M1
from minitel.render import Screen
from minitel.session import Session


def run_page(page_object, services=None):
    registry = Registry()
    registry.add(page_object)
    session = Session(
        registry,
        M1,
        initial=page_object.number,
        fallback=page_object,
        services=services or {},
    )
    return session.start()


class PageContextTests(unittest.TestCase):
    def test_declared_service_is_available(self):
        marker = object()

        @page("970", requires=("sports",))
        def paged(ctx):
            self.assertIs(ctx.service("sports"), marker)
            return Screen()

        run_page(paged, {"sports": marker})

    def test_undeclared_service_raises(self):
        @page("971")
        def paged(ctx):
            ctx.service("sports")
            return Screen()

        with self.assertRaises(KeyError):
            run_page(paged, {"sports": object()})

    def test_session_and_raw_services_are_not_exposed(self):
        @page("972")
        def paged(ctx):
            self.assertFalse(hasattr(ctx, "session"))
            self.assertFalse(hasattr(ctx, "services"))
            return Screen()

        run_page(paged)


if __name__ == "__main__":
    unittest.main()
