import time

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen


@page("901", title="TEST CARD", back_page="190")
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
    s.text(15, 0, time.strftime("DATE: %d/%m/%Y  TIME: %H:%M"))
    s.text(23, 0, "PRESS ANY KEY")
    return s
