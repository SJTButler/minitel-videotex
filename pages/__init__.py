from minitel.pagemodel import Registry

from .common.header import StatusHeader

INITIAL = "100"
GUIDE = "130"
NOT_FOUND = "__not_found__"
DEFAULT_SCREENSAVER = "clock"
HEADER = StatusHeader()


def build_registry(*extra_packages):
    registry = Registry().discover(__name__)
    for package_name in extra_packages:
        registry.discover(package_name, on_conflict="override")
    return registry
