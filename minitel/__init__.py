"""Minitel 1 Videotex library."""

__version__ = "0.3.0"

from . import text
from .data import cache, http, services
from .data.cache import ResourceCache, Snapshot
from .data.http import HttpError, JsonResponse, get_json, get_json_response
from .data.services import ServiceRegistry, ServiceSpec, service
from .design import Carousel, InputField, Pager
from .pagemodel import (
    LINE_FIELD,
    FunctionPage,
    Page,
    PageContext,
    Registry,
    page,
)
from .protocol import codec
from .render import Cell, Screen, render_diff, render_screen
from .session import Action, Screensaver, Session
from .terminal.power import PowerSignals
from .terminal.profiles import (
    M1,
    M1C,
    M2_COLOUR,
    M2_MONO,
    TerminalProfile,
    by_type,
    cps,
)
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
    "render_diff",
    "render_screen",
    "service",
    "services",
    "text",
]
