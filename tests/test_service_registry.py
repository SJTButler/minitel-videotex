import unittest

from minitel.data.services import ServiceRegistry, ServiceSpec, service


class SpecTests(unittest.TestCase):
    def test_decorator_returns_spec(self):
        @service(" demo ", description="demo service")
        def build():
            return object()

        self.assertIsInstance(build, ServiceSpec)
        self.assertEqual(build.key, "demo")
        self.assertEqual(build.description, "demo service")
        self.assertIsNotNone(build.factory())

    def test_rejects_bad_keys_and_factories(self):
        with self.assertRaises(TypeError):
            service("")
        with self.assertRaises(TypeError):
            service("x")(None)


class RegistryTests(unittest.TestCase):
    def test_mapping_behaviour(self):
        one = object()
        two = object()
        registry = ServiceRegistry({"one": one})
        registry.register("two", two)

        self.assertEqual(len(registry), 2)
        self.assertIs(registry["one"], one)
        self.assertIs(registry.get("two"), two)
        self.assertEqual(set(registry), {"one", "two"})
        self.assertEqual(set(registry.keys()), {"one", "two"})

    def test_duplicate_and_invalid_registration(self):
        registry = ServiceRegistry()
        registry.register("one", object())
        with self.assertRaises(ValueError):
            registry.register("one", object())
        with self.assertRaises(TypeError):
            registry.register("", object())
        with self.assertRaises(TypeError):
            registry.register("two", None)

    def test_discovery_imports_and_builds(self):
        registry = ServiceRegistry()
        registry.discover("services")
        self.assertIn("hackernews", registry)
        self.assertIn("weather", registry)
        self.assertIn("sports", registry)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_and_reverse_stop_order(self):
        events = []

        class Service:
            def __init__(self, name):
                self.name = name

            def start(self):
                events.append(f"{self.name}:start")

            def stop(self):
                events.append(f"{self.name}:stop")

        registry = ServiceRegistry()
        registry.register("one", Service("one"))
        registry.register("two", Service("two"))
        await registry.start()
        await registry.stop()

        self.assertEqual(
            events,
            ["one:start", "two:start", "two:stop", "one:stop"],
        )

    async def test_stop_continues_after_a_failure_and_raises_the_first(self):
        events = []

        class Service:
            def __init__(self, name, fail=False):
                self.name = name
                self.fail = fail

            def stop(self):
                events.append(f"{self.name}:stop")
                if self.fail:
                    raise RuntimeError(self.name)

        registry = ServiceRegistry()
        registry.register("one", Service("one"))
        registry.register("two", Service("two", fail=True))

        with self.assertRaises(RuntimeError):
            await registry.stop()

        self.assertEqual(events, ["two:stop", "one:stop"])

    async def test_async_hooks_and_missing_hooks(self):
        events = []

        class AsyncService:
            async def start(self):
                events.append("async:start")

            async def stop(self):
                events.append("async:stop")

        class NoHooks:
            pass

        registry = ServiceRegistry()
        registry.register("none", NoHooks())
        registry.register("async", AsyncService())
        await registry.start()
        await registry.stop()

        self.assertEqual(events, ["async:start", "async:stop"])


if __name__ == "__main__":
    unittest.main()
