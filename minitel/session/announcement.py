"""Session announcement polling and source-call logging."""

ANNOUNCEMENT_SEEN_LIMIT = 512


class AnnouncementMixin:
    def _announcements_enabled(self):
        policy = getattr(self, "announcement_policy", None)
        if policy is None or not policy.enabled:
            return False
        if (
            getattr(self, "screensaver_active", False)
            and not policy.on_screensaver
        ):
            return False
        return True

    def _reschedule_announcements(self, now=None, *, immediate=False):
        if not self._announcements_enabled():
            self._announcement_next = None
            return
        if now is None:
            now = self.clock()
        policy = self.announcement_policy
        self._announcement_next = now if immediate else now + policy.poll

    def _reset_announcement_baseline(self):
        self._announcement_seen.clear()
        self._announcement_seeded_channels.clear()
        self._announcement_since = self.wall_clock()

    def _remember_announcement(self, key):
        self._announcement_seen[key] = None
        while len(self._announcement_seen) > ANNOUNCEMENT_SEEN_LIMIT:
            self._announcement_seen.pop(next(iter(self._announcement_seen)))

    def _announcement_delay(self, now):
        if not self._announcements_enabled():
            return None
        if self._announcement_next is None:
            return None
        return max(0.0, self._announcement_next - now)

    def _announcement_due(self, now):
        return (
            self._announcements_enabled()
            and self._announcement_next is not None
            and now >= self._announcement_next
        )

    def _poll_announcements(self):
        if not self._announcements_enabled():
            self._announcement_next = None
            return
        from ..pagemodel.announcement import AnnounceContext

        now = self.clock()
        for channel, page, provider in self.registry.announcers():
            seeding = channel not in self._announcement_seeded_channels
            try:
                values = tuple(provider(AnnounceContext(self, page)))
            except Exception as exc:
                self.log(
                    f"ANNOUNCE {channel} <- {page.number} ERROR "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            new_count = 0
            for announcement in values:
                try:
                    key = (channel, announcement.key)
                    if key in self._announcement_seen:
                        continue
                    self._remember_announcement(key)
                except TypeError:
                    self.log(
                        f"ANNOUNCE {channel} <- {page.number} ERROR "
                        "unhashable announcement key"
                    )
                    continue
                if seeding:
                    continue
                at = getattr(announcement, "at", None)
                if at is not None and at <= self._announcement_since:
                    continue
                new_count += 1
            self._announcement_seeded_channels.add(channel)
            if not seeding and new_count:
                self.log(
                    f"ANNOUNCE {channel} <- {page.number}: "
                    f"{new_count} new"
                )
        self._announcement_next = now + self.announcement_policy.poll
