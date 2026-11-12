from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from ._support import store as guestbook_store
from ..common.layout import status
from ..common.messages import MessageLatch
from ..common.widgets import form_footer, line_field

GUESTBOOK_PAGE = "140"
ENTRY_LIMIT = 3


def _store(ctx):
    store = ctx.state.get("guestbook_store")
    if store is None:
        store = guestbook_store.GuestbookStore()
        ctx.add_resource(store)
        ctx.state["guestbook_store"] = store
    return store


def submit_form(ctx, values):
    handle = values.get("handle", "").strip()
    message = values.get("message", "").strip()
    latch = MessageLatch(ctx)

    if not handle:
        latch.set("HANDLE REQUIRED")
        ctx.focus("handle")
        return GUESTBOOK_PAGE
    if not message:
        latch.set("MESSAGE REQUIRED")
        ctx.focus("message")
        return GUESTBOOK_PAGE

    try:
        _store(ctx).add(handle, message)
    except ValueError:
        latch.set("MESSAGE REQUIRED")
        ctx.focus("message")
        return GUESTBOOK_PAGE

    latch.clear()
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
    ctx.set_status("PAGE 140")
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

    error = MessageLatch(ctx).text() or ""
    if error:
        s.text(18, 0, error)

    form_footer(s, ctx, [("handle", "HANDLE"), ("message", "MESSAGE")])
    return s
