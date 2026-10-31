import unittest

from minitel.cache import ResourceCache, Snapshot


class Clock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


class Factory:
    def __init__(self, run=True):
        self.run = run
        self.calls = 0

    def __call__(self, target, args):
        self.calls += 1
        run = self.run

        class Thread:
            def start(self):
                if run:
                    target(*args)

        return Thread()


class CacheTests(unittest.TestCase):
    def test_snapshot_never_loaded(self):
        snapshot = Snapshot()
        self.assertFalse(snapshot.has_value)
        self.assertIsNone(snapshot.age())

    def test_fresh_hit_does_not_load(self):
        clock = Clock()
        cache = ResourceCache(ttl=60, clock=clock)
        cache.load_now("k", lambda: "value")

        factory = Factory()
        cache.thread_factory = factory
        snapshot = cache.get("k", lambda: "other")
        self.assertEqual(snapshot.value, "value")
        self.assertFalse(snapshot.loading)
        self.assertEqual(factory.calls, 0)

    def test_ttl_expiry_loads_again(self):
        clock = Clock()
        factory = Factory()
        cache = ResourceCache(ttl=60, clock=clock, thread_factory=factory)
        cache.load_now("k", lambda: "old")

        clock.now = 61
        cache.get("k", lambda: "new")
        self.assertEqual(factory.calls, 1)
        self.assertEqual(cache.snapshot("k").value, "new")

    def test_get_returns_loading_without_blocking(self):
        clock = Clock()
        factory = Factory(run=False)
        cache = ResourceCache(clock=clock, thread_factory=factory)
        snapshot = cache.get("k", lambda: "value")
        self.assertTrue(snapshot.loading)
        self.assertEqual(factory.calls, 1)

    def test_duplicate_gets_start_one_loader(self):
        clock = Clock()
        factory = Factory(run=False)
        cache = ResourceCache(clock=clock, thread_factory=factory)
        cache.get("k", lambda: "value")
        cache.get("k", lambda: "value")
        self.assertEqual(factory.calls, 1)

    def test_stale_on_error_keeps_value(self):
        clock = Clock()
        factory = Factory()
        cache = ResourceCache(ttl=10, clock=clock, thread_factory=factory)
        cache.load_now("k", lambda: "good")

        clock.now = 11

        def fail():
            raise RuntimeError("offline")

        cache.get("k", fail)
        snapshot = cache.snapshot("k")
        self.assertEqual(snapshot.value, "good")
        self.assertIsInstance(snapshot.error, RuntimeError)
        self.assertFalse(snapshot.loading)

    def test_loaded_none_is_distinct_from_never_loaded(self):
        clock = Clock()
        cache = ResourceCache(ttl=60, clock=clock)
        cache.load_now("k", lambda: None)
        snapshot = cache.snapshot("k")
        self.assertTrue(snapshot.has_value)
        self.assertIsNone(snapshot.value)

        factory = Factory()
        cache.thread_factory = factory
        cache.get("k", lambda: "value")
        self.assertEqual(factory.calls, 0)

    def test_retry_backoff(self):
        clock = Clock()
        factory = Factory()
        cache = ResourceCache(retry_delay=60, clock=clock, thread_factory=factory)

        def fail():
            raise RuntimeError("offline")

        cache.get("k", fail)
        self.assertEqual(factory.calls, 1)
        self.assertIsNotNone(cache.snapshot("k").error)

        clock.now = 30
        cache.get("k", fail)
        self.assertEqual(factory.calls, 1)

        clock.now = 61
        cache.get("k", fail)
        self.assertEqual(factory.calls, 2)

    def test_retry_backoff_after_failure_with_cached_value(self):
        clock = Clock()
        factory = Factory()
        cache = ResourceCache(
            ttl=3600, retry_delay=60, clock=clock, thread_factory=factory
        )
        cache.load_now("k", lambda: "good")

        def fail():
            raise RuntimeError("offline")

        clock.now = 10
        cache.load_now("k", fail)
        self.assertEqual(cache.snapshot("k").value, "good")
        self.assertIsNotNone(cache.snapshot("k").error)

        clock.now = 40
        cache.get("k", fail)
        self.assertEqual(factory.calls, 0)

        clock.now = 71
        cache.get("k", fail)
        self.assertEqual(factory.calls, 1)

    def test_retry_clears_backoff(self):
        clock = Clock()
        factory = Factory()
        cache = ResourceCache(retry_delay=60, clock=clock, thread_factory=factory)

        def fail():
            raise RuntimeError("offline")

        cache.get("k", fail)
        self.assertEqual(factory.calls, 1)

        clock.now = 10
        cache.retry("k", fail)
        self.assertEqual(factory.calls, 2)

    def test_lru_bound(self):
        clock = Clock()
        cache = ResourceCache(max_entries=2, clock=clock)
        cache.load_now("a", lambda: "A")
        clock.now = 1
        cache.load_now("b", lambda: "B")
        clock.now = 2
        cache.load_now("c", lambda: "C")

        self.assertFalse(cache.snapshot("a").has_value)
        self.assertTrue(cache.snapshot("b").has_value)
        self.assertTrue(cache.snapshot("c").has_value)

    def test_load_now_returns_snapshot(self):
        clock = Clock()
        cache = ResourceCache(clock=clock)
        snapshot = cache.load_now("k", lambda: "value")
        self.assertEqual(snapshot.value, "value")
        self.assertTrue(snapshot.has_value)
        self.assertFalse(snapshot.loading)


if __name__ == "__main__":
    unittest.main()
