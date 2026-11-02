"""Service registry and declaration for long-lived background services."""

import importlib
import inspect
import pkgutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    factory: Callable[[], object]
    description: str = ""


def service(key, *, description=""):
    if not isinstance(key, str) or not key.strip():
        raise TypeError("service key must be a non-empty string")

    def decorator(factory):
        if not callable(factory):
            raise TypeError("service factory must be callable")
        return ServiceSpec(key.strip(), factory, description)

    return decorator


class ServiceRegistry(Mapping):
    def __init__(self, services=None):
        self._services = {}
        if services:
            for key, value in services.items():
                self.register(key, value)

    def register(self, key, service):
        if not isinstance(key, str) or not key.strip():
            raise TypeError("service key must be a non-empty string")
        key = key.strip()
        if key in self._services:
            raise ValueError(f"service key {key!r} already registered")
        if service is None:
            raise TypeError("service must not be None")
        self._services[key] = service
        return service

    def __getitem__(self, key):
        return self._services[key]

    def __iter__(self):
        return iter(self._services)

    def __len__(self):
        return len(self._services)

    def discover(self, package_name):
        specs = []
        self._collect_specs(package_name, specs)

        seen = {}
        for spec in sorted(specs, key=lambda item: item.key):
            if spec.key in seen:
                raise ValueError(
                    f"service key {spec.key!r} declared by "
                    f"{seen[spec.key]!r} and {spec!r}"
                )
            seen[spec.key] = spec
            self.register(spec.key, spec.factory())
        return self

    def _collect_specs(self, module_name, specs):
        module = importlib.import_module(module_name)
        for value in vars(module).values():
            if isinstance(value, ServiceSpec) and not any(
                value is existing for existing in specs
            ):
                specs.append(value)
        for module_info in sorted(
            pkgutil.iter_modules(getattr(module, "__path__", ())),
            key=lambda info: info.name,
        ):
            self._collect_specs(
                f"{module_name}.{module_info.name}", specs
            )

    async def start(self):
        for service in self._services.values():
            await self._call(service, "start")

    async def stop(self):
        errors = []
        for service in reversed(tuple(self._services.values())):
            try:
                await self._call(service, "stop")
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    async def _call(self, service, name):
        hook = getattr(service, name, None)
        if hook is None:
            return
        result = hook()
        if inspect.isawaitable(result):
            await result
