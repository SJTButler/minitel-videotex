"""983: silent idle-connection test.

This page declares no tick and no screensaver, so the session sends nothing
after the first paint. Leave the Minitel on it long enough for a NAT or WiFi
idle timeout, then press a key. If the key is ignored while the server still
reports an established connection, the TCP path died and the server has no
keepalive to notice.
"""

from minitel.pagemodel import page
from minitel.protocol import codec
from minitel.render import Screen
from minitel.text import fit

from pages.common.layout import footer, status

PAGE = "983"


def _screen():
    s = Screen()
    status(s, f"PAGE {PAGE}")
    s.text(1, 0, "IDLE / CONNECTION", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THIS PAGE IS COMPLETELY SILENT.")
    s.text(5, 0, "LEAVE IT IDLE FOR 10-30 MINUTES.")
    s.text(6, 0, "THEN PRESS A KEY.")
    s.text(8, 0, "IF THE KEY IS IGNORED, THE TCP PATH")
    s.text(9, 0, "DIED (WIFI/NAT) BUT THE SERVER STILL")
    s.text(10, 0, "THINKS THE SESSION IS CONNECTED.")
    s.text(12, 0, "RESET THE DONGLE WITH CTRL-R OR")
    s.text(13, 0, "CONNEXION/FIN TO RECONNECT.")
    s.text(15, 0, fit("ON THE SERVER: SS -TNP | GREP 3615", 40))
    s.text(17, 0, f"{PAGE} DIAGNOSTIC PAGE")
    footer(s)
    return s


@page(
    PAGE,
    title="IDLE",
    no_screensaver=True,
    back_page="199",
)
def idle(ctx):
    return _screen()
