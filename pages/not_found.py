from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from .common.layout import footer, status
from .common.widgets import page_input


@page("__not_found__", title="NOT FOUND")
def not_found(ctx):
    s = Screen()
    status(s, "PAGE ?")
    s.text(1, 0, "NOT FOUND", inverse=True, size=codec.DOUBLE_WIDTH)
    safe = "".join(ch for ch in ctx.last_key[:20] if 0x20 <= ord(ch) <= 0x7E)
    s.text(3, 0, f"NO PAGE: {safe}")
    s.text(5, 0, "TYPE A PAGE NUMBER, OR 0 FOR HOME.")
    page_input(s, ctx)
    footer(s)
    return s
