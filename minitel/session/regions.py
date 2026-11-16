"""Focusable region state for pane pages."""

from dataclasses import dataclass, field

from ..design.choice import Choice
from ..design.field import InputField
from ..design.pager import Pager
from ..design.region import Region


@dataclass
class RegionState:
    definition: Region
    cursor: Choice | Pager | None = None
    key: object | None = None
    fields: tuple[InputField, ...] = field(default_factory=tuple)
    committed: object | None = None

    @property
    def is_form(self):
        return bool(self.fields)
