"""Small shared helpers for the sports pages."""

from services.sports.models import FeedSnapshot


def service(ctx):
    return ctx.service("sports")


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


def find_matches(feed_snapshot, token):
    if feed_snapshot is None or not token:
        return ()
    token = str(token).strip().upper()
    matches = tuple(feed_snapshot.matches)
    if len(token) <= 3:
        return tuple(
            match for match in matches
            if token in (match.home.short, match.away.short)
        )
    found = []
    for index in range(2, len(token) - 1):
        home = token[:index]
        away = token[index:]
        for match in matches:
            if {home, away} == {match.home.short, match.away.short}:
                if match not in found:
                    found.append(match)
    return tuple(found)
