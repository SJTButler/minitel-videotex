from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import footer, page_input, status


@page("__not_found__", title="NOT FOUND")
def not_found(ctx):
    s = Screen()
    status(s, "PAGE ?")
    s.text(1, 0, "NOT FOUND", inverse=True, size=codec.DOUBLE_WIDTH)
    safe = "".join(ch for ch in ctx.last_key[:20] if 0x20 <= ord(ch) <= 0x7E)
    s.text(3, 0, f"NO PAGE: {safe}")
    s.text(5, 0, "TRY 1, 2, OR 3.")
    page_input(s, ctx)
    footer(s)
    return s
