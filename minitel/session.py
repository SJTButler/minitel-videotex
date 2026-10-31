"""Transport-neutral session: input, navigation, history, and page rendering."""

from dataclasses import dataclass

from . import codec
from .pages import Page, PageContext
from .screen import Screen


@dataclass
class Action:
    raw: bytes = b""
    screen: Screen | None = None
    page: Page | None = None


class Session:
    def __init__(self, registry, profile, *, initial="100", fallback=None,
                 guide=None, echo=False):
        self.registry = registry
        self.profile = profile
        self.initial = initial
        self.fallback = fallback or registry.get(initial)
        self.guide = guide
        self.echo = echo
        self.parser = codec.InputParser()
        self.line = ""
        self.last_key = ""
        self.state = {}
        self.history = []
        self.current = registry.resolve(initial)
        self.input = None

    def _cursor_visible(self):
        if self.input is None:
            return False
        if self.input.cursor == "auto":
            return bool(self.line)
        return self.input.cursor == "visible"

    def start(self):
        return self.render()

    def render(self):
        ctx = PageContext(self, self.current, self.registry)
        screen = self.current.render(ctx)
        if not isinstance(screen, Screen):
            raise TypeError(
                f"page {self.current.number!r} returned {type(screen)!r}, expected Screen"
            )
        self.input = ctx.input
        if self.input is not None:
            screen.set_cursor(
                self.input.row, self.input.col, self._cursor_visible()
            )
        else:
            screen.set_cursor(24, 0, False)
        return screen

    def resolve_page(self, value):
        if isinstance(value, Page):
            return value
        if isinstance(value, str):
            return self.registry.get(value)
        return None

    def navigate(self, value, *, push=True):
        page = self.resolve_page(value)
        if page is None:
            page = self.fallback
        if push and page is not self.current:
            self.history.append(self.current)
        self.current = page
        self.line = ""
        return Action(screen=self.render(), page=page)

    def submit(self):
        line = self.line.strip()
        self.last_key = line
        ctx = PageContext(self, self.current, self.registry)
        page = self.resolve_page(self.current.on_submit(ctx, line))
        if page is None:
            page = self.registry.get(line)
        if page is None:
            page = self.fallback
        return self.navigate(page)

    def back(self):
        self.line = ""
        if self.history:
            self.current = self.history.pop()
        else:
            self.current = self.registry.resolve(self.initial)
        return Action(screen=self.render(), page=self.current)

    def home(self):
        self.line = ""
        self.history.clear()
        self.current = self.registry.resolve(self.initial)
        return Action(screen=self.render(), page=self.current)

    def next_tick_delay(self):
        if self.input is not None and self.input.cursor == "auto" and self.line:
            return None
        interval = getattr(self.current, "tick_interval", None)
        if interval is None or interval <= 0:
            return None
        return interval

    def tick(self):
        if self.next_tick_delay() is None:
            return Action()
        ctx = PageContext(self, self.current, self.registry)
        frame = self.current.on_tick(ctx)
        if frame is None:
            return Action()
        if isinstance(frame, (bytes, bytearray)):
            frame = bytes(frame)
            if frame and self.input is not None:
                frame += codec.pos(self.input.row, self.input.col)
                frame += codec.cursor(self._cursor_visible())
            return Action(raw=frame)
        if isinstance(frame, Screen):
            return Action(screen=frame)
        raise TypeError(
            f"page {self.current.number!r} tick returned {type(frame)!r}; "
            "expected bytes, Screen, or None"
        )

    def handle(self, event):
        if isinstance(event, codec.Text):
            if self.input is None:
                return Action(raw=bytes([codec.BEL]))
            if len(self.line) >= self.input.width:
                return Action(raw=bytes([codec.BEL]))
            prefix = b""
            if self.input.cursor == "auto" and not self.line:
                prefix = codec.cursor(True)
            self.line += event.char
            echo = codec.text(event.char) if self.echo else b""
            return Action(raw=prefix + echo)
        if isinstance(event, codec.Enter):
            return self.submit()
        if isinstance(event, codec.Function):
            return self.function(event.name)
        if isinstance(event, codec.Key):
            ctx = PageContext(self, self.current, self.registry)
            page = self.resolve_page(self.current.on_key(ctx, event.name))
            if page is not None:
                return self.navigate(page)
            return Action()
        return Action()

    def function(self, name):
        if name == "ENVOI":
            return self.submit()
        if name == "CORRECTION":
            if self.line:
                self.line = self.line[:-1]
                raw = bytes([codec.BS, 0x20, codec.BS])
                if self.input is not None and self.input.cursor == "auto":
                    if not self.line:
                        raw += codec.cursor(False)
                return Action(raw=raw)
            return Action()
        if name == "ANNULATION":
            self.line = ""
            return Action(screen=self.render())
        if name == "SOMMAIRE":
            return self.home()
        if name == "RETOUR":
            return self.back()
        ctx = PageContext(self, self.current, self.registry)
        page = self.resolve_page(self.current.on_key(ctx, name))
        if page is not None:
            return self.navigate(page)
        if name == "GUIDE" and self.guide:
            return self.navigate(self.guide)
        return Action()

    def feed(self, data):
        return [self.handle(event) for event in self.parser.feed(data)]
