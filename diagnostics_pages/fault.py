"""984: deliberate page fault.

Type CRASH and press ENVOI to raise from the page handler. The app logs the
traceback and closes the connection, but the dongle does not reconnect, so the
Minitel appears frozen on this page. Use it to verify that a page exception is
the same failure mode as a dead connection.
"""

from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen

from pages.common.layout import status
from pages.common.widgets import form_footer, line_field

PAGE = "984"


def _screen(ctx):
    s = Screen()
    status(s, f"PAGE {PAGE}")
    s.text(1, 0, "FAULT INJECTION", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THIS PAGE CLOSES THE SESSION ON PURPOSE.")
    s.text(4, 0, "TYPE CRASH, THEN ENVOI.")
    s.text(6, 0, "THE DONGLE STAYS ON THIS PAGE AND")
    s.text(7, 0, "DOES NOT RECONNECT UNTIL RESET.")
    s.text(9, 0, "WATCH THE SERVER LOG FOR")
    s.text(10, 0, "session error: RuntimeError")
    s.text(12, 0, "RECOVER WITH CTRL-R OR CONNEXION/FIN.")
    s.text(14, 0, "NOT A NORMAL PAGE. DO NOT SAVE.")
    line_field(s, ctx, "confirm", 15, 9, 16, label="CONFIRM:")
    form_footer(s, ctx, [("confirm", "CONFIRM")])
    return s


def submit(ctx, values):
    value = values.get("confirm", "").strip().upper()
    ctx.values["confirm"] = ""
    if value == "CRASH":
        raise RuntimeError("diagnostic page fault (expected)")
    return PAGE


@page(
    PAGE,
    title="FAULT",
    form=True,
    on_form=submit,
    no_screensaver=True,
    back_page="199",
)
def fault(ctx):
    return _screen(ctx)
