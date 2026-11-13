"""Announcement values and session policy."""

from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True)
class Announcement:
    key: Hashable
    text: str
    at: float | None = None
    duration: float | None = None


@dataclass(frozen=True)
class AnnouncementPolicy:
    show: float = 12.0
    gap: float = 4.0
    poll: float = 5.0
    capacity: int = 8
    max_duration: float = 30.0
    enabled: bool = True
    on_screensaver: bool = True
