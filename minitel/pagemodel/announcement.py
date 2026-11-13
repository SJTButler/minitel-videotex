"""Read-only context passed to a page's announcement provider."""


def validate_announcement_declaration(announce, channel):
    """Validate a page's announce/channel pair.

    Returns the normalized channel, or None when there is no provider.
    """
    if announce is None:
        if channel is not None:
            raise ValueError("announce_channel requires announce")
        return None
    if not callable(announce):
        raise TypeError("announce must be callable or None")
    if channel is None:
        return None
    if not isinstance(channel, str) or not channel.strip():
        raise TypeError("announce_channel must be a non-empty string")
    channel = channel.strip()
    if not all(
        character.isascii()
        and (character.isalnum() or character in "_-")
        for character in channel
    ):
        raise TypeError(
            "announce_channel may contain only ASCII letters, digits, "
            "'_' and '-'"
        )
    return channel


def announcement_channel(page):
    """Return the resolved channel for a page, or None if it has no source."""
    if getattr(page, "announce", None) is None:
        return None
    return getattr(page, "announce_channel", None) or page.number


class AnnounceContext:
    """The narrow facade available to an ``announce`` provider.

    It intentionally has no fields, pager, viewport, navigation, or session
    mutation. Providers derive announcements from a shared service snapshot and
    per-session state only.
    """

    def __init__(self, session, page):
        self._session = session
        self.page = page
        self.state = session.state
        self.now = session.wall_clock()
        self.requires = tuple(getattr(page, "requires", ()))

    def service(self, name, default=None):
        if name not in self.requires:
            raise KeyError(
                f"page {self.page.number!r} does not declare "
                f"service {name!r}"
            )
        return self._session.services.get(name, default)
