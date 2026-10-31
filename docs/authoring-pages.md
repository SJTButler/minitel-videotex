# 11 - Authoring pages: the library API

The server is split into two layers:

```
minitel/     reusable library: codec, screen, render, profiles, page API,
             session, app, transport
pages/       the example service: layout helpers and one file per page
tests/       library and page tests
tools/       first-light server, virtual Minitel decoder
```

`minitel/` has no knowledge of `pages/`. You can point `MinitelApp` at any
registry, which makes it usable as a library rather than a single application.

## Quick start: add a page

Create `pages/hello.py`:

```python
from datetime import datetime

from minitel import Screen, codec, page

from pages.layout import footer, page_input, status


@page("200", title="HELLO")
def hello(ctx):
    s = Screen()
    status(s, "PAGE 200")
    s.text(1, 0, "HELLO", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THIS PAGE WAS ADDED IN ONE FILE.")
    s.text(5, 0, datetime.now().strftime("TIME: %H:%M:%S"))
    page_input(s, ctx)
    footer(s)
    return s
```

Restart the server. The page is auto-discovered; type `200` in the `PAGE:`
field and press `ENVOI`. To put it on the main menu, add a line in
`pages/home.py`:

```python
s.text(8, 0, "4  HELLO")
```

There is no central page list. Any `Page` object in a `pages/*.py` module is
registered by:

```python
Registry().discover("pages")
```

## The Page object

The decorator form is the shortest:

```python
@page(number, title="", aliases=(), on_submit=None, on_key=None, **meta)
def render(ctx):
    return Screen()
```

- `number` is the primary key (`"200"`).
- `aliases` are extra keys (`("4",)` or `("", "0")` for the home page).
- `title` is metadata; it is not drawn automatically.
- `on_submit(ctx, line)` handles `ENVOI`/`Enter`.
- `on_key(ctx, key)` handles keys the session does not consume (`GUIDE`,
  `SUITE`, arrows, etc.).
- `meta` is free-form; useful for a custom app.

For stateful or larger pages, subclass `Page`:

```python
from minitel import Page, Screen

class Clock(Page):
    number = "210"
    title = "CLOCK"

    def render(self, ctx):
        s = Screen()
        ...
        return s

    def on_key(self, ctx, key):
        if key == "SUITE":
            return "100"
        return None
```

## PageContext

Every `render`, `on_submit`, and `on_key` receives a `PageContext`.

| Member | Meaning |
|---|---|
| `ctx.session` | the live `Session` |
| `ctx.profile` | the terminal profile (`M1`, `M2_MONO`, ...) |
| `ctx.registry` | the `Registry` |
| `ctx.line` | the current input buffer |
| `ctx.last_key` | the last submitted line (used by the not-found page) |
| `ctx.state` | a per-session dict for page state |
| `ctx.set_input(row, col, width)` | register the input field and cursor |
| `ctx.page_for(key)` | look up another page |

`set_input` is required for typing. It tells the session where the cursor
belongs and what the maximum line length is. `pages.layout.page_input` does
both the drawing and the registration:

```python
page_input(s, ctx)
```

Without an input field, typing returns `BEL` and the cursor is parked at row
24, column 0.

## Screen and attributes

`Screen` is the intermediate representation. The renderer turns it into bytes.

```python
s = Screen()
s.text(3, 0, "HELLO")
s.fill(5, 0, 40, " ", inverse=True)
s.rule(6, 0, 40, "=")
s.field(20, 6, 10)
s.set_cursor(20, 6)
```

Coordinates are **row 0-24, column 0-39**. Row 0 is the status/header line;
rows 1-24 are content. `text` raises `ValueError` if it would overflow.

Cell attributes:

| Attribute | Values |
|---|---|
| `fg` | `codec.BLACK` ... `codec.WHITE` |
| `bg` | same |
| `inverse` | `True` / `False` |
| `flash` | `True` / `False` |
| `underline` | `True` / `False` |
| `size` | `codec.NORMAL`, `DOUBLE_HEIGHT`, `DOUBLE_WIDTH`, `DOUBLE_SIZE` |

Use `codec.text` for accents and special characters. `Screen.text` accepts
Unicode; the renderer encodes it through `codec.text` and raises on characters
the Minitel cannot represent.

For raw protocol work, `minitel.codec` exposes `pos`, `home`, `clear`, `fg`,
`bg`, `inverse`, `flash`, `underline`, `size`, `repeat`, `mosaic`, `cursor`,
and the input parser. Most pages should not need it beyond constants.

## Layout helpers

`pages/layout.py` is the shared theme:

- `status(s, "PAGE 200")` paints the full inverse top row and keeps the page
  number clear of the terminal's `F/C` indicator.
- `footer(s)` writes the key hints at row 22.
- `page_input(s, ctx)` draws `PAGE:` at row 20 and registers the field.

Use these for consistency. A different service can copy the file or provide its
own layout package and pass its registry to `MinitelApp`.

## Input, submit, navigation

The session handles the common keys:

| Key | Behaviour |
|---|---|
| `ENVOI` / `Enter` | call `on_submit`, then route the line |
| `CORRECTION` | remove one character, send `BS`, space, `BS` |
| `ANNULATION` | clear the line, rerender the current page |
| `SOMMAIRE` | go to `INITIAL`, clear history |
| `RETOUR` | pop history, or go to `INITIAL` |
| `GUIDE` | page's `on_key`, then the app's guide page |

`on_submit` can return:

- a page key (`"110"`),
- a `Page` object,
- `None`, in which case the session looks up the submitted line in the registry.

Example stateful page:

```python
def echo_submit(ctx, line):
    ctx.state["echo"] = line
    return "220"

@page("220", title="ECHO", on_submit=echo_submit)
def echo(ctx):
    s = Screen()
    status(s, "PAGE 220")
    s.text(3, 0, "LAST: " + ctx.state.get("echo", ""))
    page_input(s, ctx)
    footer(s)
    return s
```

Returning `"220"` rerenders the same page. `Session.navigate` does not push
duplicate history when the target is the current page.

`on_key` receives `GUIDE`, `SUITE`, `REPETITION`, arrows, and other keys after
the session's built-in handling. Return a key or `Page` to navigate.

## Aliases and the menu

`@page("110", aliases=("1",))` lets the user type either `1` or `110`. The home
page uses `aliases=("", "0")`, so an empty submit and `0` both go home.

Keep page numbers stable and descriptive. The example scheme is:

| Number | Page |
|---|---|
| `100` | home / index |
| `110` | news |
| `120` | weather |
| `130` | about / guide |
| `__not_found__` | fallback |

## Testing a page

The session is transport-neutral, so a page can be tested without a socket:

```python
import pages
from minitel import M1, Session

registry = pages.build_registry()
session = Session(
    registry,
    M1,
    initial="200",
    fallback=registry.get(pages.NOT_FOUND),
)
screen = session.start()
assert screen.rows[1][0].ch == "H"

actions = session.feed(b"1" + bytes([0x13, 0x41]))
assert session.current.number == "110"
```

For a visual check:

```sh
cd home_minitel_server
python3 -m minitel.server --port 43620 --cps 0
python3 tools/virtual_minitel.py --connect 127.0.0.1:43620 --plain
```

`--cps 0` disables pacing for a fast local test. The real M1 uses `--cps`
default (1200/9).

## Using AI to write pages

Give the model a small, concrete context:

- this document,
- `pages/home.py` and `pages/layout.py`,
- `minitel/pages.py` and `minitel/screen.py`,
- the test command.

A prompt that works well:

```
Add a Minitel page in pages/ using the existing library.
- Use @page from minitel and Screen.
- Use pages.layout.status, footer, and page_input.
- Keep to 40 columns and rows 0-24; row 0 is status, row 20 is PAGE, row 22 is footer.
- Call page_input(s, ctx) so typing is captured.
- Use ctx.state for per-session data and on_submit for forms.
- Add a menu line in pages/home.py.
- Run: python3 -m unittest discover -s tests -v
- Inspect: python3 tools/virtual_minitel.py --connect 127.0.0.1:43620 --plain
```

Review generated pages for:

- text overflow (the code raises, but check the intended layout),
- a missing `page_input`,
- unsupported characters (the renderer raises),
- duplicate page numbers or aliases,
- the status row and `PAGE:` field placement.

One page per file is the easiest review unit. Keep page logic in `pages/` and
reusable behaviour in `minitel/`.

## Extending beyond pages

The library boundaries are deliberate:

- **New terminal profile**: add a `TerminalProfile` and a `by_type` mapping in
  `minitel/profiles.py`.
- **New transport**: implement `serve`/`paced_write` in
  `minitel/transport.py`; `Session` does not know about sockets.
- **Different application**: build a `Registry`, pass a fallback and guide page
  to `MinitelApp`, and choose a page package (not necessarily `pages/`).
- **Background services**: the current app is request-driven. A clock, chat, or
  live feed needs a scheduler/hub above `Session`; the `Action` and `Session`
  boundaries are the place to add it.
- **Forms**: `InputField` and `on_submit` are the start. Multiple fields,
  validation, and masks are natural extensions of `Session`.
- **Themes**: copy `pages/layout.py` or create another layout package. The core
  renderer does not contain the `3615 KILO` status bar.

## Rules of thumb

- 40 columns, 24 content rows. Row 0 is the terminal's status area.
- One idea per page.
- Use inverse and double width for hierarchy, not decoration.
- Keep the `PAGE:` field at row 20 and the footer at row 22.
- Design uppercase-first; accents cost three bytes each.
- Prefer `REP`-friendly runs (the renderer already compresses runs of 3+).
- Test on the M1 and with the virtual Minitel.
- Keep `minitel/` free of application content; keep `pages/` free of protocol
  byte wrangling.
