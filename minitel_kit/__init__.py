"""Optional drawing helpers built on top of ``minitel.Screen``.

This package is deliberately outside ``minitel/``. It is a convenience layer
for pages that want tables and clipped panes, not part of the core contract.
A service can import it, replace it, or draw the same geometry itself.
"""

from .pane import Rect
from .table import Column, Table

__all__ = ["Column", "Rect", "Table"]
