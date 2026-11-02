from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from ..common.clock import clock_hm, date_text


@page("901", title="TEST CARD", back_page="190", screensaver="test_card")
def mire(ctx):
    s = Screen()
    s.text(0, 0, "TEST CARD 3615 KILO")

    s.text(2, 0, "PALETTE:")
    for index in range(8):
        s.fill(2, 10 + index * 3, 3, " ", fg=index, bg=index)

    s.text(4, 0, "TEXTE: ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    s.text(5, 0, "       0123456789 .,:;!?")

    s.text(7, 0, "DOUBLE:")
    s.text(7, 8, "BIG", size=codec.DOUBLE_WIDTH)

    s.text(9, 0, "INVERSE", inverse=True)
    s.text(9, 12, "UNDERLINE", underline=True)
    s.text(9, 26, "NORMAL")

    s.rule(11, 0, 40, "-")

    s.text(13, 0, "PROFILE: " + ctx.profile.name.upper())
    s.text(14, 0, f"MAX: {ctx.profile.max_speed} BPS")
    s.text(15, 0, f"DATE: {date_text()}  TIME: {clock_hm()}")
    s.text(23, 0, "PRESS ANY KEY")
    return s
