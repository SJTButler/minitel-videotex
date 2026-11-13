from minitel.pagemodel import page
from minitel.render import Screen

TOP = 3
LEFT = 4
BOTTOM = 18
RIGHT = 35
BALL = "O"
STATE_KEY = "screensaver_ball"


def _state(ctx):
    state = ctx.state.get(STATE_KEY)
    if state is None:
        state = {"row": 10, "col": 20, "dr": 1, "dc": 1}
        ctx.state[STATE_KEY] = state
    return state


def _draw(ctx):
    state = _state(ctx)
    s = Screen()
    s.text(0, 0, "3615 KILO / BOUNCING BALL")

    for row in range(TOP, BOTTOM + 1):
        s.put(row, LEFT, "|")
        s.put(row, RIGHT, "|")
    for col in range(LEFT, RIGHT + 1):
        s.put(TOP, col, "-")
        s.put(BOTTOM, col, "-")
    for row, col in ((TOP, LEFT), (TOP, RIGHT), (BOTTOM, LEFT), (BOTTOM, RIGHT)):
        s.put(row, col, "+")

    s.put(state["row"], state["col"], BALL)
    s.text(23, 0, "PRESS ANY KEY")
    return s


def _move(state):
    row = state["row"] + state["dr"]
    col = state["col"] + state["dc"]
    if row <= TOP + 1 or row >= BOTTOM - 1:
        state["dr"] *= -1
        row = state["row"] + state["dr"]
    if col <= LEFT + 1 or col >= RIGHT - 1:
        state["dc"] *= -1
        col = state["col"] + state["dc"]
    state["row"] = row
    state["col"] = col


def ball_tick(ctx):
    _move(_state(ctx))
    return _draw(ctx)


@page("903", title="BOUNCING BALL", tick_interval=1.0, on_tick=ball_tick,
      back_page="190", screensaver="bouncing_ball", paint="cell")
def ball(ctx):
    return _draw(ctx)
