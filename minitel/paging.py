"""Paging arithmetic for fixed-size result windows."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pager:
    total: int
    page_size: int
    offset: int = 0

    def __post_init__(self):
        if self.page_size <= 0:
            raise ValueError("page_size must be positive")
        if self.total < 0:
            raise ValueError("total must not be negative")

    @property
    def page_count(self):
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def page_index(self):
        if not self.page_count:
            return 0
        return min(max(0, self.offset) // self.page_size, self.page_count - 1)

    @property
    def page_number(self):
        if not self.page_count:
            return 0
        return self.page_index + 1

    @property
    def label(self):
        return f"{self.page_number}/{self.page_count}"

    def clamp(self):
        if not self.page_count:
            return Pager(self.total, self.page_size, 0)
        last = (self.page_count - 1) * self.page_size
        return Pager(self.total, self.page_size, min(max(0, self.offset), last))

    def window(self, items):
        offset = self.clamp().offset
        return tuple(items[offset:offset + self.page_size])

    def next(self, wrap=False):
        if not self.page_count:
            return Pager(self.total, self.page_size, 0)
        offset = self.clamp().offset + self.page_size
        if offset >= self.total:
            offset = 0 if wrap else (self.page_count - 1) * self.page_size
        return Pager(self.total, self.page_size, offset)

    def prev(self, wrap=False):
        if not self.page_count:
            return Pager(self.total, self.page_size, 0)
        offset = self.clamp().offset - self.page_size
        if offset < 0:
            offset = (self.page_count - 1) * self.page_size if wrap else 0
        return Pager(self.total, self.page_size, offset)
