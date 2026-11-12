"""Header API: row-0 chrome composed with a body page."""


class Header:
    """An app-selected row-0 view.

    A header is not a page. It has no number, alias, history, fields, or
    navigation. Instances are shared across sessions, so per-session state must
    live in ``HeaderContext.state``.
    """

    tick_interval = None
    requires = ()

    def render(self, ctx):
        """Return a Screen whose row 0 is the header, or None to pass through.

        Only row 0 of the returned Screen is composed. Returning None leaves
        the body page's row 0 untouched.
        """
        raise NotImplementedError

    def announcement_duration(self, announcement):
        """Return an optional duration for the current announcement."""
        return None


def header_requires(header):
    """Validate a header declaration and return its service requirements."""
    if header is None or header is False:
        return ()
    if not isinstance(header, Header):
        raise TypeError("header must be None, False, or a Header instance")
    requires = getattr(header, "requires", ())
    if isinstance(requires, str) or any(
        not isinstance(key, str) or not key.strip()
        for key in requires
    ):
        raise TypeError("header requires must be a sequence of service keys")
    interval = getattr(header, "tick_interval", None)
    if interval is not None and (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or interval <= 0
    ):
        raise TypeError("header tick_interval must be a positive number or None")
    return tuple(key.strip() for key in requires)


class HeaderContext:
    """Read-only context passed to a Header for rendering."""

    def __init__(self, session, page, registry, *, header, body_row,
                 status_text=None):
        self._session = session
        self.body_page = page
        self.registry = registry
        self.header = header
        self.body_row = tuple(body_row)
        self.status_text = status_text
        self.state = session.state
        self.profile = session.profile
        self.screensaver_active = bool(session.screensaver_active)
        self.now = session.wall_clock()
        self.requires = (
            tuple(getattr(page, "requires", ()))
            + header_requires(header)
        )

    def service(self, name, default=None):
        if name not in self.requires:
            raise KeyError(
                f"header on page {self.body_page.number!r} does not declare "
                f"service {name!r}"
            )
        return self._session.services.get(name, default)

    @property
    def announcement(self):
        return getattr(self._session, "announcement", None)

    @property
    def announcement_channel(self):
        return getattr(self._session, "announcement_channel", None)

    @property
    def announcement_elapsed(self):
        return getattr(self._session, "announcement_elapsed", 0.0)
