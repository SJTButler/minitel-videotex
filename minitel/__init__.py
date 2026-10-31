"""Minitel 1 Videotex library."""

__version__ = "0.2.0"

from . import cache, codec, http, paging, text
from .cache import ResourceCache, Snapshot
from .http import HttpError, get_json
from .paging import Pager
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
    "HttpError",
    "InputField",
    "MinitelApp",
    "Page",
    "PageContext",
    "Pager",
    "Registry",
    "ResourceCache",
    "Screen",
    "Session",
    "Snapshot",
    "TerminalProfile",
    "by_type",
    "cache",
    "codec",
    "cps",
    "get_json",
    "http",
    "page",
    "paging",
    "render",
    "render_diff",
    "text",
]
