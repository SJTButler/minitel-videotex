"""Sports announcement source for the public live pages."""

from minitel import Announcement

from services.sports.models import alert_key

from .labels import alert_text
from .state import configured, service

SPORTS_CHANNEL = "sports"


def collect_goal_alerts(ctx):
    feed = service(ctx)
    if not configured(feed):
        return ()
    snapshot = feed.snapshot()
    if not snapshot.has_value:
        return ()
    return tuple(
        Announcement(
            key=alert_key(alert),
            text=alert_text(alert),
            at=alert.at.timestamp(),
        )
        for alert in snapshot.alerts
        if alert.kind == "GOAL"
    )
