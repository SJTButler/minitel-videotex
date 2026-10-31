from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from . import guestbook_store
from .layout import footer, status

GUESTBOOK_PAGE = "140"
MESSAGE_PAGE = "141"
ENTRY_LIMIT = 3


def _store(ctx):
    store = ctx.state.get("guestbook_store")
    if store is None:
        store = guestbook_store.GuestbookStore()
        ctx.state["guestbook_store"] = store
    return store


def _error(ctx):
    return ctx.state.get("guestbook_error", "")


def submit_handle(ctx, line):
    handle = line.strip()
    if not handle:
        ctx.state["guestbook_error"] = "HANDLE REQUIRED"
        return GUESTBOOK_PAGE
    ctx.state["guestbook_handle"] = handle[:16]
    ctx.state.pop("guestbook_error", None)
    return MESSAGE_PAGE


def submit_message(ctx, line):
    message = line.strip()
    if not message:
        ctx.state["guestbook_error"] = "MESSAGE REQUIRED"
        return MESSAGE_PAGE
    try:
        _store(ctx).add(ctx.state.get("guestbook_handle", "ANON"), message)
    except ValueError:
        ctx.state["guestbook_error"] = "MESSAGE REQUIRED"
        return MESSAGE_PAGE
    ctx.state.pop("guestbook_error", None)
    return GUESTBOOK_PAGE


@page(GUESTBOOK_PAGE, title="GUESTBOOK", aliases=("4",), on_submit=submit_handle)
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
    s.text(14, 0, "HANDLE:")
    s.field(14, 8, 16)
    ctx.set_input(14, 8, 16)
    error = _error(ctx)
    if error:
        s.text(16, 0, error)
    footer(s)
    return s


@page(MESSAGE_PAGE, title="MESSAGE", on_submit=submit_message, transient=True)
def message(ctx):
    s = Screen()
    status(s, "PAGE 141")
    s.text(1, 0, "MESSAGE", inverse=True, size=codec.DOUBLE_WIDTH)
    handle = ctx.state.get("guestbook_handle", "ANON")
    s.text(3, 0, f"FROM: {handle}"[:40])
    s.text(5, 0, "TYPE YOUR MESSAGE, THEN ENVOI:")
    s.field(7, 0, 38)
    ctx.set_input(7, 0, 38)
    error = _error(ctx)
    if error:
        s.text(9, 0, error)
    footer(s)
    return s
