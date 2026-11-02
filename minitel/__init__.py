"""Minitel 1 Videotex library."""

__version__ = "0.2.0"

from . import cache, codec, http, paging, services, text
from .cache import ResourceCache, Snapshot
from .http import HttpError, JsonResponse, get_json, get_json_response
from .carousel import Carousel
from .paging import Pager
from .power import PowerSignals
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
from .render import render_diff, render_screen
from .pages import (
    LINE_FIELD,
    FunctionPage,
    InputField,
    Page,
    PageContext,
    Registry,
    page,
)
from .services import ServiceRegistry, ServiceSpec, service
from .screensaver import Screensaver
from .session import Action, Session
from .app import MinitelApp

__all__ = [
    "M1",
    "M1C",
    "M2_COLOUR",
    "M2_MONO",
    "Action",
    "Carousel",
    "Cell",
    "FunctionPage",
    "HttpError",
    "InputField",
    "JsonResponse",
    "LINE_FIELD",
    "MinitelApp",
    "Page",
    "PageContext",
    "Pager",
    "PowerSignals",
    "Registry",
    "ResourceCache",
    "Screen",
    "Screensaver",
    "ServiceRegistry",
    "ServiceSpec",
    "Session",
    "Snapshot",
    "TerminalProfile",
    "by_type",
    "cache",
    "codec",
    "cps",
    "get_json",
    "get_json_response",
    "http",
    "page",
    "paging",
    "render_diff",
    "render_screen",
    "service",
    "services",
    "text",
]
