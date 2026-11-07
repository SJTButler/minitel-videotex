"""Declarative input-field value."""

from dataclasses import dataclass


@dataclass
class InputField:
    name: str
    row: int
    col: int
    width: int
    mask: str | None = None
    value: str = ""
    cursor: str = "visible"
    live: bool = False
    visible: bool = True
