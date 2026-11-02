import time
import unittest

from pages.common.layout import SECONDARY, WARNING
from pages.common.service_status import (
    ServiceState,
    classify,
    classify_many,
    colour_for,
    describe,
    describe_many,
)
from minitel.cache import Snapshot
from services.sports.models import FeedSnapshot


class ClassifyTests(unittest.TestCase):
    def test_snapshot_states(self):
        self.assertIs(classify(None), ServiceState.MISSING)
        self.assertIs(
            classify(Snapshot(loading=True)), ServiceState.LOADING
        )
        self.assertIs(
            classify(Snapshot(error=RuntimeError("down"))),
            ServiceState.UNAVAILABLE,
        )
        self.assertIs(
            classify(
                Snapshot(
                    value=("story",),
                    loaded_at=time.monotonic(),
                    error=RuntimeError("down"),
                )
            ),
            ServiceState.STALE,
        )
        self.assertIs(
            classify(
                Snapshot(value=(), loaded_at=time.monotonic()),
                empty=True,
            ),
            ServiceState.EMPTY,
        )
        self.assertIs(
            classify(Snapshot(value=("story",), loaded_at=time.monotonic())),
            ServiceState.READY,
        )

    def test_feed_snapshot_does_not_need_a_value_attribute(self):
        snapshot = FeedSnapshot(matches=(), loaded_at=time.monotonic())
        self.assertIs(classify(snapshot), ServiceState.READY)
        self.assertIs(classify(snapshot, empty=True), ServiceState.EMPTY)

    def test_many(self):
        ready = Snapshot(value=("a",), loaded_at=time.monotonic())
        stale = Snapshot(
            value=("b",),
            loaded_at=time.monotonic(),
            error=RuntimeError("down"),
        )
        failed = Snapshot(error=RuntimeError("down"))
        self.assertIs(classify_many(()), ServiceState.MISSING)
        self.assertIs(classify_many((Snapshot(loading=True),)), ServiceState.LOADING)
        self.assertIs(classify_many((failed,)), ServiceState.UNAVAILABLE)
        self.assertIs(classify_many((ready,)), ServiceState.READY)
        self.assertIs(classify_many((ready, stale)), ServiceState.STALE)


class ColourTests(unittest.TestCase):
    def test_error_states_warn(self):
        for state in (
            ServiceState.MISSING,
            ServiceState.UNAVAILABLE,
            ServiceState.STALE,
        ):
            self.assertEqual(colour_for(state), WARNING)
        for state in (
            ServiceState.LOADING,
            ServiceState.EMPTY,
            ServiceState.READY,
        ):
            self.assertEqual(colour_for(state), SECONDARY)


class DescribeTests(unittest.TestCase):
    def test_single_snapshot_copy(self):
        ready = Snapshot(value=("a",), loaded_at=time.monotonic())
        stale = Snapshot(
            value=("a",),
            loaded_at=time.monotonic(),
            error=RuntimeError("down"),
        )
        self.assertEqual(
            describe(None, missing_text="NOT CONFIGURED").text,
            "NOT CONFIGURED",
        )
        self.assertEqual(
            describe(Snapshot(loading=True), loading_text="LOADING").text,
            "LOADING",
        )
        self.assertEqual(
            describe(
                Snapshot(error=RuntimeError("down")),
                unavailable_text="UNAVAILABLE",
            ).text,
            "UNAVAILABLE",
        )
        self.assertTrue(
            describe(ready, updated_prefix="UPDATED").text.startswith("UPDATED ")
        )
        self.assertTrue(
            describe(stale, stale_prefix="OFFLINE").text.startswith("OFFLINE ")
        )
        self.assertEqual(
            describe(
                Snapshot(value=(), loaded_at=time.monotonic()),
                empty=True,
                empty_text="NO HEADLINES",
            ).text,
            "NO HEADLINES",
        )

    def test_many_snapshot_copy(self):
        ready = Snapshot(value=("a",), loaded_at=time.monotonic())
        stale = Snapshot(
            value=("a",),
            loaded_at=time.monotonic(),
            error=RuntimeError("down"),
        )
        self.assertEqual(
            describe_many((), missing_text="NO WEATHER LOCATIONS").text,
            "NO WEATHER LOCATIONS",
        )
        self.assertEqual(
            describe_many(
                (Snapshot(loading=True),),
                loading_text="LOADING WEATHER...",
            ).text,
            "LOADING WEATHER...",
        )
        self.assertEqual(
            describe_many(
                (Snapshot(error=RuntimeError("down")),),
                unavailable_text="WEATHER UNAVAILABLE",
            ).text,
            "WEATHER UNAVAILABLE",
        )
        self.assertTrue(
            describe_many((ready,), updated_prefix="UPDATED")
            .text.startswith("UPDATED ")
        )
        self.assertTrue(
            describe_many((ready, stale), stale_prefix="OFFLINE - CACHED")
            .text.startswith("OFFLINE - CACHED ")
        )


if __name__ == "__main__":
    unittest.main()
