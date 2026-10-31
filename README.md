# Minitel Videotex library

A small Python library and example service for Minitel 1/2 terminals. It speaks
Minitel-native Videotex (CEPT Profile 2) and borrows Prestel's page model:
numbered pages, a status line, an input field, history, and a guide page.

The Minitel 1 is the primary target. The M2 profiles are present, but the M2 is
monochrome and currently parked.

## Layout

```
minitel/       reusable, content-free library
  codec.py     bytes, attributes, input parser
  profiles.py  M1/M2 capability profiles
  screen.py    25x40 screen model
  render.py    screen -> Videotex bytes
  pages.py     Page, PageContext, Registry, @page
  session.py   input, navigation, history
  app.py       registry + profile + session + transport
  transport.py TCP and paced writes
pages/         example service, one file per page, auto-discovered
tests/         library and page tests
tools/         first-light server and virtual Minitel decoder
docs/          authoring guide
```

## Development environment

The project is configured for uv. `.python-version` pins Python 3.12,
`uv.lock` locks the environment, and `.venv/` is local and ignored. There are
no runtime dependencies.

```sh
uv sync
```

`pyproject.toml` uses `[tool.uv] package = false` while the example service
lives in the repository. Building and publishing the library as a package is a
separate step.

## Quick start

Requires Python 3.10+.

```sh
uv sync
uv run python -m minitel.server --port 3615
```

The server listens on `0.0.0.0:3615`, sends the welcome page, and paces output
at 1200/9 chars per second for the M1. Point the dongle's Telnet preset at the
server's LAN address and port.

If the terminal's local echo is off:

```sh
uv run python -m minitel.server --port 3615 --echo
```

Server echo is recommended for dynamic/tick pages: it serialises key echo with
clock updates. Disable local echo first, otherwise characters are doubled. See
`docs/authoring-pages.md` for the tradeoff.

`--cps 0` disables pacing for a local test.

## Tests

```sh
uv run python -m unittest discover -s tests -v
```

The renderer tests decode the emitted bytes with `tools/virtual_minitel.py`, so
they check the screen rather than just byte strings.

## Library

```python
from minitel import Screen, codec, page

@page("200", title="HELLO")
def hello(ctx):
    s = Screen()
    s.text(1, 0, "HELLO", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "ADD A PAGE IN ONE FILE.")
    s.field(20, 6, 10)
    ctx.set_input(20, 6, 10)
    return s
```

A page returns a `Screen`; `ctx.set_input(row, col, width)` tells the session
where the cursor and input line belong. `PageContext` also provides
`ctx.line`, `ctx.last_key`, `ctx.state`, `ctx.profile`, and `ctx.registry`.

For a multi-field form, register fields with `ctx.add_field(...)`, set
`form=True`, and implement `on_form(ctx, values)`. `SUITE`/`RETOUR` move focus;
`RETOUR` at the first field goes back. The guestbook page is the reference
example.

Partial updates use `render.render_diff` and `Session.refresh()`. Field echo,
corrections, and focus keep the shadow screen in sync; a `Screen` returned by
`on_tick` is diffed against that shadow. Raw tick frames remain available for
tiny regions. Form focus re-renders and diffs, so `form_footer(s, ctx, fields)`
can change its hints per field using `ctx.active_name`.

The example service's layout helpers are in `pages/layout.py`. The application
is wired in `minitel/server.py` with `MinitelApp`, so a different service can
pass its own registry and page package without touching the library.

## Adding pages

The full guide is in [`docs/authoring-pages.md`](docs/authoring-pages.md).

Short version: create `pages/your_page.py`, use `@page(...)`, return a `Screen`,
and call `page_input(s, ctx)` if you want typing. Restart the server; pages are
discovered automatically.

## Tools

- `tools/hello.py` - first-light TCP server with terminal probes and key logging.
- `tools/virtual_minitel.py` - decode a Videotex stream into a 25x40 grid.

```sh
uv run python tools/virtual_minitel.py --demo --plain
uv run python tools/virtual_minitel.py --connect 127.0.0.1:3615 --plain
```

## Scope

- M1: 40 columns, 1200 baud, monochrome, 7E1; the active target.
- M2: profiles and 9600/color/DRCS/80-column capability modelling exist, but
  the M2 is not currently connected.
- Prestel is a design reference, not a wire profile.

This repository is the public code level. Hardware notes, research, vendored
repositories, and personal setup live in the private outer workspace.
