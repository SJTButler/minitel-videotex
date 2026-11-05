"""Background services shared by pages and owned by the server."""

from minitel.data.services import ServiceRegistry, ServiceSpec, service


def build_registry(*extra_packages, package="services"):
    registry = ServiceRegistry().discover(package)
    for package_name in extra_packages:
        registry.discover(package_name)
    return registry


__all__ = ["ServiceRegistry", "ServiceSpec", "build_registry", "service"]
