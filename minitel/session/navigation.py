"""Session navigation and history."""

from ..pagemodel.model import ExtensionPage, Page, PageContext
from .action import Action


class NavigationMixin:
    def resolve_page(self, value):
        if isinstance(value, Page):
            return value
        if isinstance(value, str):
            return self.registry.get(value)
        return None

    def navigate(self, value, *, push=True):
        self.screensaver_active = False
        self._touch()
        page = self.resolve_page(value)
        if page is None:
            page = self.fallback
        if page.number != self.current.number:
            if push:
                if self.current.transient:
                    if self.history and self.history[-1].number == page.number:
                        self.history.pop()
                else:
                    self.history.append(self.current)
            self._reset_page()
            self._extension_pending = isinstance(page, ExtensionPage)
            self.current = page
            screen = self.render()
            self._shadow_exact = True
            return Action(screen=screen, page=page)
        self.current = page
        return self.refresh()

    def submit(self):
        line = self.line.strip()
        self.last_key = line
        ctx = PageContext(self, self.current, self.registry)
        values = dict(self.values)
        if callable(self.current.on_form):
            result = self.current.on_form(ctx, values)
        else:
            result = self.current.on_submit(ctx, line)
        requested = self._take_screensaver_request()
        if requested is not None:
            return requested
        page = self.resolve_page(result)
        if page is None and not self.current.form:
            page = self.registry.get(line)
        if page is None:
            page = self.fallback
        return self.navigate(page)

    def _back_or_parent(self):
        target = self.resolve_page(self.current.back_page)
        if target is not None and target.number != self.current.number:
            history_top = self.history[-1] if self.history else None
            at_parent = history_top is not None and (
                history_top.number == target.number
                or getattr(history_top, "base", None) is target
            )
            if not at_parent:
                return self.navigate(target, push=False)
        return self.back()

    def back(self):
        self.screensaver_active = False
        self._touch()
        if self.history:
            self.current = self.history.pop()
        else:
            self.current = self.registry.resolve(self.initial)
        self._reset_page()
        self._extension_pending = False
        screen = self.render()
        self._shadow_exact = True
        return Action(screen=screen, page=self.current)

    def home(self):
        self.screensaver_active = False
        self._touch()
        self.history.clear()
        self.current = self.registry.resolve(self.initial)
        self._reset_page()
        self._extension_pending = False
        screen = self.render()
        self._shadow_exact = True
        return Action(screen=screen, page=self.current)
