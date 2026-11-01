"""Small shared helpers for the sports pages."""

from services.sports.models import FeedSnapshot


def service(ctx):
    return ctx.services.get("sports")


def snapshot(ctx):
    feed = service(ctx)
    if feed is None:
        return FeedSnapshot(error="NOT CONFIGURED")
    return feed.snapshot()


def configured(feed):
    return feed is not None and getattr(feed, "configured", False)


def find_match(feed_snapshot, match_id):
    if feed_snapshot is None or match_id is None:
        return None
    for match in feed_snapshot.matches:
        if match.id == match_id:
            return match
    return None


def clear_error(ctx):
    ctx.state.pop("sports_error", None)
    ctx.state.pop("sports_error_offset", None)


def set_error(ctx, message, offset=0):
    ctx.state["sports_error"] = message
    ctx.state["sports_error_offset"] = offset
