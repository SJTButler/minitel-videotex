"""Background services shared by pages and owned by the server."""

from minitel.data.services import ServiceRegistry, ServiceSpec, service


def build_registry(package="services"):
    return ServiceRegistry().discover(package)


__all__ = ["ServiceRegistry", "ServiceSpec", "build_registry", "service"]
