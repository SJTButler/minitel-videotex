"""985: deterministic announcement source.

Load the diagnostics package, open this page, and set MODE to ON. The page
declares an announcement provider that emits a test banner every 15 seconds on
any page in the session, so the header and chyron path can be exercised without
a live sports feed.
"""

from minitel import Announcement
from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen

from pages.common.widgets import form_footer, line_field

PAGE = "985"
ANNOUNCE_ON = "diagnostic_announce_on"
ANNOUNCE_STARTED = "diagnostic_announce_started"
INTERVAL = 15.0


def _announce(ctx):
    if not ctx.state.get(ANNOUNCE_ON, False):
        return ()
    started = float(ctx.state.get(ANNOUNCE_STARTED, ctx.now))
    bucket = int(max(0.0, ctx.now - started) // INTERVAL)
    return (
        Announcement(
            key=("diagnostic", started, bucket),
            text=f"TEST ANNOUNCEMENT {bucket + 1}",
            at=started + bucket * INTERVAL,
        ),
    )


def _screen(ctx):
    on = bool(ctx.state.get(ANNOUNCE_ON, False))
    s = Screen()
    ctx.set_status(f"PAGE {PAGE}")
    s.text(1, 0, "ANNOUNCEMENT TEST", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THIS PAGE EMITS A TEST BANNER")
    s.text(4, 0, f"EVERY {int(INTERVAL)} SECONDS WHILE ON.")
    s.text(6, 0, "SET ON, THEN GO TO ANY PAGE.")
    s.text(7, 0, "THE SESSION KEEPS PRODUCING THEM.")
    s.text(9, 0, fit_state(on))
    s.text(12, 0, "MODE ON OR OFF, THEN ENVOI.")
    line_field(s, ctx, "mode", 14, 7, 10, label="MODE:")
    form_footer(s, ctx, [("mode", "MODE")])
    return s


def fit_state(on):
    return f"STATE: {'ON' if on else 'OFF'}"


def submit(ctx, values):
    value = values.get("mode", "").strip().upper()
    if value in ("ON", "START", "GO"):
        ctx.state[ANNOUNCE_ON] = True
        ctx.state[ANNOUNCE_STARTED] = ctx.now
    elif value in ("OFF", "STOP", "QUIT"):
        ctx.state[ANNOUNCE_ON] = False
    ctx.values["mode"] = ""
    return PAGE


@page(
    PAGE,
    title="ANNOUNCE",
    form=True,
    on_form=submit,
    announce=_announce,
    announce_channel="diagnostics",
    no_screensaver=True,
    back_page="199",
)
def announce(ctx):
    return _screen(ctx)
