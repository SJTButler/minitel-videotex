"""Session action value."""

from dataclasses import dataclass

from ..pagemodel.model import Page
from ..render.screen import Screen


@dataclass
class Action:
    raw: bytes = b""
    screen: Screen | None = None
    page: Page | None = None
    power: bool | None = None
