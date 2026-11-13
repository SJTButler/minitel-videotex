"""Session announcement polling, queueing, and caller logging."""

from ..design.announcement import Announcement
from ..text import sanitize

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
        self._clear_announcements()
        self._announcement_seen.clear()
        self._announcement_seeded_channels.clear()
        self._announcement_since = self.wall_clock()

    def _remember_announcement(self, key):
        self._announcement_seen[key] = None
        while len(self._announcement_seen) > ANNOUNCEMENT_SEEN_LIMIT:
            self._announcement_seen.pop(next(iter(self._announcement_seen)))

    def _clear_current_announcement(self):
        self.announcement = None
        self.announcement_channel = None
        self._announcement_source_page = None
        self._announcement_started = None
        self._announcement_show_until = None

    def _clear_announcements(self, *, drop_queue=True):
        self._clear_current_announcement()
        self._announcement_next_show = None
        if drop_queue:
            self._announcement_queue.clear()

    @property
    def announcement_elapsed(self):
        if self.announcement is None or self._announcement_started is None:
            return 0.0
        return max(0.0, self.clock() - self._announcement_started)

    def _announcement_duration(self, announcement):
        policy = self.announcement_policy
        duration = (
            announcement.duration
            if announcement.duration is not None
            else policy.show
        )
        header = self._header_for(self.display_page)
        if header is not None:
            try:
                suggested = header.announcement_duration(announcement)
            except Exception as exc:
                self.log(
                    "ANNOUNCE duration ERROR "
                    f"{type(exc).__name__}: {exc}"
                )
                suggested = None
            if suggested is not None:
                duration = suggested
        return min(max(1.0, float(duration)), policy.max_duration)

    def _enqueue_announcements(self, items, now):
        if not items:
            return
        items.sort(
            key=lambda item: (
                item[2].at is None,
                item[2].at if item[2].at is not None else 0.0,
            )
        )
        self._announcement_queue.extend(items)
        capacity = self.announcement_policy.capacity
        while len(self._announcement_queue) > capacity:
            self._announcement_queue.pop(0)
        if self.announcement is None and self._announcement_next_show is None:
            self._announcement_next_show = now

    def _advance_announcements(self, now):
        policy = self.announcement_policy
        if policy is None or not policy.enabled:
            return False
        changed = False
        if (
            self.announcement is not None
            and self._announcement_show_until is not None
            and now >= self._announcement_show_until
        ):
            if self.announcement_channel is not None:
                number = (
                    self._announcement_source_page.number
                    if self._announcement_source_page is not None
                    else "?"
                )
                self.log(
                    f"ANNOUNCE hide {self.announcement_channel} <- {number}"
                )
            self._clear_current_announcement()
            self._announcement_next_show = now + policy.gap
            changed = True

        if self.announcement is not None or not self._announcement_queue:
            return changed
        if self._has_input_text():
            self._announcement_next_show = now + policy.poll
            return changed
        if self._announcement_next_show is None:
            self._announcement_next_show = now
        if now < self._announcement_next_show:
            return changed
        if self._header_for(self.display_page) is None:
            self._announcement_next_show = now + policy.poll
            return changed

        channel, page, announcement = self._announcement_queue.pop(0)
        duration = self._announcement_duration(announcement)
        self.announcement = announcement
        self.announcement_channel = channel
        self._announcement_source_page = page
        self._announcement_started = now
        self._announcement_show_until = now + duration
        self._announcement_next_show = None
        self.log(f"ANNOUNCE show {channel} <- {page.number}")
        return True

    def _announcement_delay(self, now):
        if not self._announcements_enabled():
            return None
        delays = []
        if self.announcement is not None and self._announcement_show_until:
            delays.append(max(0.0, self._announcement_show_until - now))
        if self.announcement is None and self._announcement_queue:
            next_show = self._announcement_next_show
            delays.append(
                max(0.0, (next_show if next_show is not None else now) - now)
            )
        if self._announcement_next is not None:
            delays.append(max(0.0, self._announcement_next - now))
        return min(delays) if delays else None

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
        new_items = []
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
                if not isinstance(announcement, Announcement):
                    self.log(
                        f"ANNOUNCE {channel} <- {page.number} ERROR "
                        "provider returned a non-Announcement value"
                    )
                    continue
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
                at = announcement.at
                if at is not None and at <= self._announcement_since:
                    continue
                text = sanitize(announcement.text)
                if not text:
                    continue
                new_items.append(
                    (
                        channel,
                        page,
                        Announcement(
                            key=announcement.key,
                            text=text,
                            at=announcement.at,
                            duration=announcement.duration,
                        ),
                    )
                )
                new_count += 1
            self._announcement_seeded_channels.add(channel)
            if not seeding and new_count:
                self.log(
                    f"ANNOUNCE {channel} <- {page.number}: "
                    f"{new_count} new"
                )
        self._enqueue_announcements(new_items, now)
        self._announcement_next = now + self.announcement_policy.poll
