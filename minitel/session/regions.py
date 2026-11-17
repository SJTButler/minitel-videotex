"""Focusable region state for pane pages."""

from dataclasses import dataclass, field
from typing import Callable

from ..design.choice import Choice
from ..design.field import InputField
from ..design.pager import Pager
from ..design.region import MainRegion, Region


@dataclass
class RegionState:
    definition: Region | MainRegion
    cursor: Choice | Pager | None = None
    key: object | None = None
    fields: tuple[InputField, ...] = field(default_factory=tuple)
    items: tuple[object, ...] | None = None
    commit: Callable | None = None
    committed: object | None = None
    active: bool = True
    remove: Callable | None = None
    commands: dict | None = None

    @property
    def is_form(self):
        return bool(self.fields)
