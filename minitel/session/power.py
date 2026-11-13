"""Session power pause and resume."""

from .action import Action


class PowerMixin:
    def pause(self):
        if self.paused:
            return Action()
        self.paused = True
        self.parser = self._new_parser()
        self.power.reset()
        self._clear_announcements()
        return Action(power=False)

    def resume(self):
        now = self.clock()
        self.paused = False
        self.parser = self._new_parser()
        self.power.reset()
        self._last_body_tick = now
        self._reset_announcement_baseline()
        self._reschedule_announcements(now, immediate=True)
        self._touch()
        if self.screensaver_active:
            self._screensaver_since = now
            action = self._render_screensaver()
        else:
            screen = self.render()
            self._shadow_exact = True
            action = Action(screen=screen)
        action.raw = self.echo_override() + action.raw
        action.power = True
        return action
