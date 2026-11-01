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
  session.py   input, navigation, history, idle takeover
  carousel.py  timed advance policy for a page sequence
  screensaver.py idle takeover, page sequence, carousel timing
  app.py       registry + profile + session + transport + services
  transport.py TCP and paced writes
  text.py      remote text sanitising, fit/wrap, domain, age
  paging.py    fixed-size paging arithmetic
  cache.py     non-blocking cache with stale-on-error snapshots
  http.py      small synchronous JSON client
pages/         example service, one file per page, auto-discovered
  news.py      page 110, the news service directory
  news_source.py Hacker News parsing, source, and cached service
  hackernews.py  pages 111/112, headlines and story detail
  screensaver.py  page 190, the screensaver selector
  screensaver_clock.py  page 900, clock
  screensaver_mire.py   page 901, test card
  screensaver_ball.py   page 903, bouncing ball
  screensaver_promo.py  pages 910-912, carousel frames
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
`ctx.line`, `ctx.last_key`, `ctx.state`, `ctx.profile`, `ctx.registry`,
`ctx.services`, `ctx.service(name)`, and `ctx.set_pager(total, page_size)`.

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

## Live data and the news service

Long-running services are injected into the app and copied into each session:

```python
app = MinitelApp(registry, services=pages.build_services())
```

A service may define `start()` and `stop()`; either may be a normal function or
a coroutine. `MinitelApp.serve()` starts services before listening and stops
them in a `finally` block. Pages reach them through `ctx.services` or
`ctx.service("hackernews")`.

The news service is the worked example:

```
1 NEWS (home)
  -> 110 NEWS service directory
       -> 111 HACKER NEWS front-page list
            -> 112 STORY detail with one comment
```

- `pages/news_source.py` owns the Hacker News URLs, field names, parsing, and
  the cached service. The pages only see `Story` and `Comment` objects.
- `minitel/cache.py` starts at most one loader thread per key and never blocks
  the render path. A stale value is kept when a refresh fails, so the terminal
  keeps showing the last good headlines with an `OFFLINE` notice.
- Front-page data is cached for 300 seconds, comments for 1,800 seconds, and a
  failed load is retried after 60 seconds. There are no new dependencies: the
  new modules use only the standard library.
- `minitel/text.py` strips HTML, unescapes entities, transliterates typographic
  punctuation and accents, drops emoji, and wraps to the 40-column screen. Every
  remote title, author, domain, and comment goes through it before `Screen.text`.
- `minitel/paging.py` provides the `Pager` used by the four-story list.
- `minitel/http.py` provides `get_json()` and `HttpError` for cache threads.
- `pages/layout.py` exposes `BODY`, `ACCENT`, `SECONDARY`, and `WARNING`. The
  news pages use yellow story badges, cyan metadata, and magenta warnings; on
  the monochrome M1 these are grey levels.
- On `111`, `ctx.set_pager(...)` registers a session-owned cursor. `SUITE`
  advances and wraps; `RETOUR` walks back one page and only leaves the list from
  page 1, the same boundary pattern as multi-field form focus. The cursor is
  remembered per page, so returning to the list resumes the same page.
- `112` declares `back_page="111"`, so typing `112` directly returns to the list
  first, then follows the existing history.

`on_tick` may return a complete `Screen`; the session diffs it against the
shadow screen and restores the input cursor. Raw bytes remain the cheaper choice
for a single changing region.

## Screensavers

An idle session can take over the display without navigating away from the
current page. The screensaver preserves history, field values, focus, and pager
offset; any input wakes back to the same page. Idle means no input and no
navigation, so ticking pages still fall asleep.

```sh
uv run python -m minitel.server --screensaver clock
uv run python -m minitel.server --screensaver bouncing_ball --screensaver-after 60
uv run python -m minitel.server --screensaver off
```

`--screensaver` accepts `clock`, `test_card`, `bouncing_ball`, `carousel`,
`all`, or `off`. Screensaver pages declare their group with
`@page(..., screensaver="group")`; `Registry.screensaver_groups()` collects
them. `minitel/` carries a `Screensaver` with a page sequence and a `Carousel`
timing policy, but no specific page numbers. `--screensaver-after` is the idle
delay in seconds; `0` disables automatic activation but leaves manual
activation available. `--screensaver-hold` sets the seconds per page for a
multi-page screensaver.

Page `190` (`7` on the home menu) is the selector. Type `1`-`4` to choose CLOCK,
TEST CARD, BOUNCING BALL, or CAROUSEL, `6` to cycle the auto delay, and `0` to
activate immediately. The screensaver pages are `900` CLOCK, `901` TEST CARD,
`903` BOUNCING BALL, and the `910`-`912` CAROUSEL frames.

`MinitelApp(screensaver=..., screensaver_after=..., screensaver_hold=...)`
provides the same configuration for another service. Pages may call
`ctx.set_screensaver(...)` or `ctx.start_screensaver()`.

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
