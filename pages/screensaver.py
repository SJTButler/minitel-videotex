from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import ACCENT, footer, page_input, status
from .manifest import SCREENSAVER_LABELS, SCREENSAVER_MODES, SELECTABLE_SCREENSAVERS

SCREENSAVER_CHOICES = tuple(
    (SCREENSAVER_LABELS[name], SCREENSAVER_MODES[name])
    for name in SELECTABLE_SCREENSAVERS
)

DELAYS = (120.0, 300.0, 600.0, None)


def _pages(ctx, keys):
    return tuple(ctx.registry.get(key) for key in keys)


def _selected_label(ctx):
    current = ctx.screensaver
    if current is None:
        return "NONE"
    for label, keys in SCREENSAVER_CHOICES:
        if current.pages == _pages(ctx, keys):
            return label
    return "CUSTOM"


def _delay_label(after):
    if after is None or after <= 0:
        return "OFF"
    minutes = after / 60
    if minutes >= 1:
        return f"{int(minutes)} MIN"
    return f"{int(after)} SEC"


def _choose(ctx, keys):
    current = ctx.screensaver
    after = current.after if current else 120.0
    hold = current.hold if current else 20.0
    ctx.set_screensaver(keys, after=after, hold=hold)


def _ensure(ctx):
    if ctx.screensaver is None:
        _choose(ctx, SCREENSAVER_CHOICES[0][1])


def _cycle_delay(ctx):
    current = ctx.screensaver
    if current is None:
        return
    try:
        index = DELAYS.index(current.after)
    except ValueError:
        index = -1
    after = DELAYS[(index + 1) % len(DELAYS)]
    ctx.set_screensaver(current.pages, after=after, hold=current.hold)


def screensaver_submit(ctx, line):
    line = line.strip()
    ctx.values.clear()
    if line in ("1", "2", "3", "4"):
        _choose(ctx, SCREENSAVER_CHOICES[int(line) - 1][1])
    elif line == "0":
        _ensure(ctx)
        ctx.start_screensaver()
    elif line == "6":
        _ensure(ctx)
        _cycle_delay(ctx)
    return "190"


@page("190", title="SCREENSAVER", aliases=("7",), on_submit=screensaver_submit,
      back_page="100")
def screensaver(ctx):
    s = Screen()
    status(s, "PAGE 190")
    s.text(1, 0, "SCREENSAVER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "SCREENSAVER SETTINGS")

    selected = _selected_label(ctx)
    for index, (label, _) in enumerate(SCREENSAVER_CHOICES):
        row = 5 + index
        chosen = label == selected
        s.text(
            row,
            0,
            f"{'>' if chosen else ' '} {index + 1}  {label}",
            inverse=chosen,
            fg=ACCENT if chosen else codec.WHITE,
        )

    s.text(10, 0, "0  ACTIVATE NOW")

    current = ctx.screensaver
    after = current.after if current else None
    s.text(12, 0, f"CHOICE: {selected}")
    s.text(13, 0, f"AUTO: {_delay_label(after)}")
    s.text(15, 0, "1-4 SELECT   0 ACTIVATE")
    s.text(16, 0, "6 DELAY")
    page_input(s, ctx)
    footer(s)
    return s
