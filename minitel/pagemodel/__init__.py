"""Page API: pages, context, and registry."""

from ..design.field import InputField
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
    "ExtensionPage",
    "FunctionPage",
    "InputField",
    "Page",
    "PageContext",
    "Registry",
    "page",
    "split_extension",
]
