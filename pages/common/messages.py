"""Page-owned transient messages with optional pager position."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PageMessage:
    text: str
    offset: int | None = None


class MessageLatch:
    def __init__(self, ctx, key=None):
        self.ctx = ctx
        self.key = key or f"{ctx.page.number}_message"

    def set(self, text, offset=None):
        self.ctx.state[self.key] = PageMessage(text, offset)

    def clear(self):
        self.ctx.state.pop(self.key, None)

    def get(self, offset=None):
        message = self.ctx.state.get(self.key)
        if message is None:
            return None
        if (
            offset is not None
            and message.offset is not None
            and message.offset != offset
        ):
            return None
        return message

    def text(self, offset=None):
        message = self.get(offset)
        return message.text if message is not None else None

    def clear_if_moved(self, offset):
        message = self.ctx.state.get(self.key)
        if (
            message is not None
            and message.offset is not None
            and message.offset != offset
        ):
            self.clear()
