"""Minitel 1 Videotex library."""

__version__ = "0.3.0"

from . import text
from .data import cache, http, services
from .data.cache import ResourceCache, Snapshot
from .data.http import HttpError, JsonResponse, get_json, get_json_response
from .data.services import ServiceRegistry, ServiceSpec, service
from .design import (
    Announcement,
    AnnouncementPolicy,
    Carousel,
    Choice,
    InputField,
    PAGE_BACK,
    Pager,
    Region,
    Stop,
    Stops,
    Viewport,
)
from .pagemodel.errors import (
    PageDeclarationError,
    PageDeclarationKeyError,
    PageDeclarationTypeError,
)
from .pagemodel import (
    LINE_FIELD,
    AnnounceContext,
    FunctionPage,
    Header,
    HeaderContext,
    Page,
    PageContext,
    Registry,
    page,
)
from .protocol import codec
from .render import Cell, Screen, compose_row, render_diff, render_screen
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
    "AnnounceContext",
    "Announcement",
    "AnnouncementPolicy",
    "Carousel",
    "Cell",
    "Choice",
    "FunctionPage",
    "Header",
    "HeaderContext",
    "HttpError",
    "InputField",
    "JsonResponse",
    "LINE_FIELD",
    "MinitelApp",
    "Page",
    "PageContext",
    "PageDeclarationError",
    "PageDeclarationKeyError",
    "PageDeclarationTypeError",
    "PAGE_BACK",
    "Pager",
    "PowerSignals",
    "Region",
    "Registry",
    "ResourceCache",
    "Screen",
    "Screensaver",
    "ServiceRegistry",
    "ServiceSpec",
    "Session",
    "Snapshot",
    "Stop",
    "Stops",
    "TerminalProfile",
    "Viewport",
    "by_type",
    "cache",
    "codec",
    "compose_row",
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
