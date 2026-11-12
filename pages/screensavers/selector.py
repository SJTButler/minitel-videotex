from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from ..common.layout import ACCENT, footer
from ..common.widgets import page_input

DELAYS = (120.0, 300.0, 600.0, None)


def _choices(ctx):
    return tuple(
        (name.replace("_", " ").replace("-", " ").upper(), pages)
        for name, pages in ctx.registry.screensaver_groups().items()
    )


def _selected_label(ctx, choices):
    current = ctx.screensaver
    if current is None:
        return "NONE"
    for label, pages in choices:
        if current.pages == pages:
            return label
    return "CUSTOM"


def _delay_label(after):
    if after is None or after <= 0:
        return "OFF"
    minutes = after / 60
    if minutes >= 1:
        return f"{int(minutes)} MIN"
    return f"{int(after)} SEC"


def _choose(ctx, pages):
    current = ctx.screensaver
    after = current.after if current else 120.0
    hold = current.hold if current else 20.0
    wrap = current.wrap if current else True
    ctx.set_screensaver(pages, after=after, hold=hold, wrap=wrap)


def _ensure(ctx):
    if ctx.screensaver is None:
        choices = _choices(ctx)
        if choices:
            _choose(ctx, choices[0][1])


def _cycle_delay(ctx):
    current = ctx.screensaver
    if current is None:
        return
    try:
        index = DELAYS.index(current.after)
    except ValueError:
        index = -1
    after = DELAYS[(index + 1) % len(DELAYS)]
    ctx.set_screensaver(
        current.pages, after=after, hold=current.hold, wrap=current.wrap
    )


def screensaver_submit(ctx, line):
    line = line.strip()
    ctx.clear_input()
    choices = _choices(ctx)[:8]
    if line.isdigit() and 1 <= int(line) <= len(choices):
        _choose(ctx, choices[int(line) - 1][1])
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
    ctx.set_status("PAGE 190")
    s.text(1, 0, "SCREENSAVER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "SCREENSAVER SETTINGS")

    choices = _choices(ctx)
    visible = choices[:8]
    selected = _selected_label(ctx, choices)
    for index, (label, _) in enumerate(visible):
        row = 5 + index % 4
        col = 0 if index < 4 else 20
        chosen = label == selected
        s.text(
            row,
            col,
            f"{'>' if chosen else ' '} {index + 1}  {label}",
            inverse=chosen,
            fg=ACCENT if chosen else codec.WHITE,
        )

    s.text(10, 0, "0  ACTIVATE NOW")

    current = ctx.screensaver
    after = current.after if current else None
    s.text(12, 0, f"CHOICE: {selected}")
    s.text(13, 0, f"AUTO: {_delay_label(after)}")
    if visible:
        s.text(15, 0, f"1-{len(visible)} SELECT   0 ACTIVATE")
    else:
        s.text(15, 0, "0 ACTIVATE")
    s.text(16, 0, "6 DELAY")
    page_input(s, ctx)
    footer(s)
    return s
