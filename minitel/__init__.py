"""Minitel 1 Videotex library."""

__version__ = "0.2.0"

from . import codec
from .profiles import (
    M1,
    M1C,
    M2_COLOUR,
    M2_MONO,
    TerminalProfile,
    by_type,
    cps,
)
from .screen import Cell, Screen
from .render import render, render_diff
from .pages import FunctionPage, InputField, Page, PageContext, Registry, page
from .session import Action, Session
from .app import MinitelApp

__all__ = [
    "M1",
    "M1C",
    "M2_COLOUR",
    "M2_MONO",
    "Action",
    "Cell",
    "FunctionPage",
    "InputField",
    "MinitelApp",
    "Page",
    "PageContext",
    "Registry",
    "Screen",
    "Session",
    "TerminalProfile",
    "by_type",
    "codec",
    "cps",
    "page",
    "render",
    "render_diff",
]
