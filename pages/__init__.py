from minitel.pages import Registry

INITIAL = "100"
GUIDE = "130"
NOT_FOUND = "__not_found__"
DEFAULT_SCREENSAVER = "clock"


def build_registry():
    return Registry().discover(__name__)


def build_services():
    from .news.source import HackerNewsService
    from .sports.config import SportsConfig
    from .sports.feed import SportsService
    from .weather.source import WeatherService

    return {
        "hackernews": HackerNewsService(),
        "weather": WeatherService(),
        "sports": SportsService(config=SportsConfig.from_env()),
    }
