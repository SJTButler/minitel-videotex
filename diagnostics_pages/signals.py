"""982: REP, reset gestures, and power-cycle signals.

The rule below is encoded with REP (0x12). If the dongle reboots while drawing
this page, suspect TX/RX coupling, line noise, or a firmware reset path rather
than the renderer. The page also lists the two dongle reset gestures and keeps
a five-second clock so the server log can be matched to the screen.
"""

from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen

from pages.common.clock import clock_text
from pages.common.layout import footer, status

PAGE = "982"


def _screen():
    s = Screen()
    status(s, f"PAGE {PAGE}")
    s.text(1, 0, "SIGNALS / RESET", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "REP (0X12) IS SENT IN THE RULE BELOW.")
    s.rule(5, 0, 40, "=")
    s.text(6, 0, "IF THE DONGLE REBOOTS HERE, CHECK")
    s.text(7, 0, "TX/RX COUPLING OR LINE NOISE.")
    s.text(9, 0, "PRESS CONNEXION/FIN: DONGLE REBOOTS.")
    s.text(10, 0, "PRESS CTRL-R: DONGLE REBOOTS.")
    s.text(11, 0, "POWER CYCLE: SERVER PAUSES, THEN")
    s.text(12, 0, "FULL-PAINTS THIS PAGE.")
    s.text(14, 0, "SERVER TIME: " + clock_text())
    s.text(16, 0, "WATCH THE SERVER LOG FOR DISCONNECT.")
    s.text(18, 0, f"{PAGE} DIAGNOSTIC PAGE")
    footer(s)
    return s


def tick(ctx):
    return _screen()


@page(
    PAGE,
    title="SIGNALS",
    on_tick=tick,
    tick_interval=5.0,
    no_screensaver=True,
    back_page="199",
)
def signals(ctx):
    return _screen()
