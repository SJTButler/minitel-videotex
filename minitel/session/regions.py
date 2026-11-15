"""Focusable region state for pane pages."""

from dataclasses import dataclass, field

from ..design.field import InputField
from ..design.pager import Pager
from ..design.region import Region


@dataclass
class RegionState:
    definition: Region
    cursor: Pager | None = None
    key: object | None = None
    fields: tuple[InputField, ...] = field(default_factory=tuple)

    @property
    def is_form(self):
        return bool(self.fields)
