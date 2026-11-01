from minitel.pages import Registry

INITIAL = "100"
GUIDE = "130"
NOT_FOUND = "__not_found__"
DEFAULT_SCREENSAVER = "clock"


def build_registry():
    return Registry().discover(__name__)


def build_services():
    from .news_source import HackerNewsService

    return {"hackernews": HackerNewsService()}
