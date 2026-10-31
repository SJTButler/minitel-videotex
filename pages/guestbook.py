from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from . import guestbook_store
from .layout import form_footer, line_field, status

GUESTBOOK_PAGE = "140"
ENTRY_LIMIT = 3


def _store(ctx):
    store = ctx.state.get("guestbook_store")
    if store is None:
        store = guestbook_store.GuestbookStore()
        ctx.state["guestbook_store"] = store
    return store


def submit_form(ctx, values):
    handle = values.get("handle", "").strip()
    message = values.get("message", "").strip()

    if not handle:
        ctx.state["guestbook_error"] = "HANDLE REQUIRED"
        ctx.focus("handle")
        return GUESTBOOK_PAGE
    if not message:
        ctx.state["guestbook_error"] = "MESSAGE REQUIRED"
        ctx.focus("message")
        return GUESTBOOK_PAGE

    try:
        _store(ctx).add(handle, message)
    except ValueError:
        ctx.state["guestbook_error"] = "MESSAGE REQUIRED"
        ctx.focus("message")
        return GUESTBOOK_PAGE

    ctx.state.pop("guestbook_error", None)
    ctx.values.clear()
    ctx.focus("handle")
    return GUESTBOOK_PAGE


@page(
    GUESTBOOK_PAGE,
    title="GUESTBOOK",
    aliases=("4",),
    form=True,
    on_form=submit_form,
)
def guestbook(ctx):
    s = Screen()
    status(s, "PAGE 140")
    s.text(1, 0, "GUESTBOOK", inverse=True, size=codec.DOUBLE_WIDTH)

    entries = _store(ctx).recent(ENTRY_LIMIT)
    if not entries:
        s.text(3, 0, "NO ENTRIES YET. BE THE FIRST.")
    for i, entry in enumerate(entries):
        row = 3 + i * 3
        s.text(row, 0, f"{entry.handle[:16]:<16} {entry.created_at}"[:40])
        s.text(row + 1, 0, entry.message[:40])

    s.text(12, 0, "SIGN THE GUESTBOOK")
    line_field(s, ctx, "handle", 14, 9, 16, label="HANDLE:")
    line_field(s, ctx, "message", 16, 9, 30, label="MESSAGE:")

    error = ctx.state.get("guestbook_error", "")
    if error:
        s.text(18, 0, error)

    form_footer(s)
    return s
