"""Compatibility re-exports for the shared presentation helpers.

New page code should import from ``pages.common.layout``,
``pages.common.widgets``, and ``pages.common.service_status``.
"""

from .common.layout import (
    ACCENT,
    BODY,
    FIELD_COL,
    FIELD_ROW,
    FIELD_WIDTH,
    SECONDARY,
    STATUS_MARGIN,
    WARNING,
    footer,
    key_footer,
    status,
)
from .common.service_status import updated_label
from .common.widgets import form_footer, line_field, page_input

__all__ = [
    "ACCENT",
    "BODY",
    "FIELD_COL",
    "FIELD_ROW",
    "FIELD_WIDTH",
    "SECONDARY",
    "STATUS_MARGIN",
    "WARNING",
    "footer",
    "form_footer",
    "key_footer",
    "line_field",
    "page_input",
    "status",
    "updated_label",
]
