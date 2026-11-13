"""Page API: pages, context, and registry."""

from ..design.field import InputField
from .announcement import AnnounceContext, announcement_channel
from .header import Header, HeaderContext, header_requires
from .model import (
    LINE_FIELD,
    MAX_EXTENSION_LENGTH,
    ExtensionPage,
    FunctionPage,
    Page,
    PageContext,
    Registry,
    page,
    split_extension,
)

__all__ = [
    "LINE_FIELD",
    "MAX_EXTENSION_LENGTH",
    "AnnounceContext",
    "ExtensionPage",
    "FunctionPage",
    "Header",
    "HeaderContext",
    "InputField",
    "Page",
    "PageContext",
    "Registry",
    "announcement_channel",
    "header_requires",
    "page",
    "split_extension",
]
