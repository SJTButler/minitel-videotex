# Minitel Videotex library

A small Python library and example service for Minitel 1 terminals. It speaks
Minitel-native Videotex (CEPT Profile 2) and borrows Prestel's page model:
numbered pages, a status line, an input field, history, and a guide page.

The Minitel 1 is the active and only supported runtime profile: 40x25, 1200
baud, grey palette. The M2 profile models are reserved for future capability
work; detection, per-session speed, colour, DRCS, and 80-column mixed mode are
not wired.

## Layout

```
minitel/       reusable, content-free library
  protocol/codec.py    bytes, attributes, input parser
  terminal/profiles.py M1/M2 capability profiles
  terminal/power.py    terminal power-off pause and power-on repaint
  render/screen.py     25x40 screen model
  render/render.py     screen -> Videotex bytes
  design/pager.py      fixed-size paging arithmetic
  design/carousel.py   timed advance policy for a page sequence
  design/field.py      declarative input field
  pagemodel/model.py   Page, PageContext, Registry, @page
  session/core.py      Session orchestration: start/render/tick/handle/feed
  session/navigation.py history, back_page, submit
  session/editing.py   field focus, text editing, shadow cursor
  session/idle.py      screensaver, idle timing, pager carousel
  session/power.py     pause and resume
  session/action.py    Action
  session/screensaver.py Screensaver: pages, idle delay, carousel
  data/cache.py        non-blocking cache with stale-on-error snapshots
  data/http.py         small synchronous JSON client
  data/services.py     ServiceRegistry, ServiceSpec, @service
  app.py               registry + profile + session + transport + services
  transport.py         TCP and connection-level pacing
  text.py              remote text sanitising, fit/wrap, domain, age
run_server.py  example CLI wiring: pages + services + MinitelApp
services/      background services, auto-discovered
  common/
    config.py    .env loader and shared env helpers
  news/
    service.py   Hacker News source, cache, and service
  weather/
    service.py   Open-Meteo source, cache, and service
  sports/
    config.py    football-data.org configuration
    models.py    provider-neutral Match, Team, Goal, and FeedSnapshot
    source.py    football-data.org parsing and HTTP source
    feed.py      one shared poller, alerts, quota, and standings cache
pages/         example site, auto-discovered
  common/      shared presentation: layout, widgets, status, messages, clock
  home.py      page 100
  about.py     page 130
  not_found.py fallback
  page_directory.py page 199, hidden developer directory
  news/
    directory.py page 110, the news service directory
    hackernews.py pages 111/112, headlines and story detail
  weather/
    page.py      page 120, current conditions, forecast, and 120#CODE city detail
    _support/
      labels.py  condition labels
  sports/
    live.py      page 150, league pages, kickoff groups, vidiprinter,
                 next-matchday fallback
    detail.py    page 151, match detail
    tables.py    page 153, league tables
    status.py    page 154, feed status
    _support/
      state.py   service adapters and snapshot helpers
      layout.py  sports formatting and geometry
      labels.py  competition labels and alert text
  screensavers/
    selector.py  page 190
    clock.py     page 900
    test_card.py page 901
    scroll.py    page 902, scrolling public-domain text
    ball.py      page 903
    promos.py    pages 910-912
    _support/
      text.py    loads and wraps the bundled public-domain text
      texts/     public-domain source text
  guestbook/
    page.py      page 140
    _support/
      store.py   SQLite storage
tests/         library, service, and page tests
tools/         server probes, virtual Minitel decoder, interactive client
docs/          authoring guide
```

## Development environment

The project is configured for uv. `.python-version` pins Python 3.12,
`uv.lock` locks the environment, and `.venv/` is local and ignored. There are
no runtime dependencies.

```sh
uv sync
```

`pyproject.toml` builds the installable `minitel-videotex` library from
`minitel/`; the example server, pages, services, tools, and tests stay in the
source repository. There are no runtime dependencies.

```sh
python -m unittest discover -s tests -v
```

## Quick start

Requires Python 3.10+.

```sh
uv sync
uv run python run_server.py --port 3615
```

The server listens on `0.0.0.0:3615`, sends the welcome page, and paces output
at 1200/9 chars per second for the M1. Point the dongle's Telnet preset at the
server's LAN address and port.

Server-side echo is the default: the server echoes keys and asserts local echo
off on connect and again after a power-on, so you do not need to change the
dongle/terminal setting first. It is recommended for dynamic/tick pages because
it serialises key echo with clock updates.

To use the terminal's local echo instead:

```sh
uv run python run_server.py --port 3615 --local-echo
```

See `docs/authoring-pages.md` for the tradeoff.

`--cps 0` disables pacing for a local test.

To drive the server from this machine instead of a real terminal:

```sh
uv run python tools/minitel_client.py --connect 127.0.0.1:3615
```

The client uses local echo by default. Because the server now defaults to
server echo, start the client with `--no-local-echo` to avoid doubled
characters. If the server runs with `--local-echo`, the client default matches.
Use `--cps 0` on the server for an immediate local paint.

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
`ctx.line`, `ctx.input_value`, `ctx.clear_input()`, `ctx.last_key`, `ctx.state`,
`ctx.profile`, `ctx.registry`, `ctx.service(name)` (declared services only),
`ctx.add_resource(resource)`, and `ctx.set_pager(total, page_size)`.

For a multi-field form, register fields with `ctx.add_field(...)`, set
`form=True`, and implement `on_form(ctx, values)`. `SUITE`/`RETOUR` move focus;
`RETOUR` at the first field goes back. The guestbook page is the reference
example. Its SQLite store is registered with `ctx.add_resource` and closes when
the connection ends.

Partial updates use `render.render_diff` and `Session.refresh()`. Field echo,
corrections, and focus keep the shadow screen in sync; a `Screen` returned by
`on_tick` is diffed against that shadow. Raw tick frames remain available for
tiny regions. Form focus re-renders and diffs, so `form_footer(s, ctx, fields)`
can change its hints per field using `ctx.active_name`.

The example service's shared presentation helpers are in `pages/common/`
(`layout`, `widgets`, `service_status`, `messages`, and `clock`). Feature-private
helpers live under `pages/<feature>/_support/`; the top level of each feature
contains only page modules. The application is wired in `run_server.py` with
`MinitelApp`, so a different service can pass its own registry and page package
without touching the library.

## Live data and services

Long-running services live under `services/` and are discovered by the server:

```python
page_registry = pages.build_registry()
service_registry = services.build_registry()
missing = page_registry.missing_requirements(service_registry)
app = MinitelApp(page_registry, services=service_registry)
```

Each service package declares a cheap builder with `@service("key")`; the
factory must not perform network I/O. `ServiceRegistry` starts services before
listening and stops them in reverse order in a `finally` block. `start()` and
`stop()` are optional and may be normal functions or coroutines.

Pages declare their dependencies:

```python
@page("150", title="LIVE SCORES", requires=("sports",))
```

The server refuses to start if a required service key is missing. Pages reach
declared services through `ctx.service("sports")`; undeclared keys raise
`KeyError`. `services/` is app infrastructure; `minitel/` remains content-free;
`pages/` remains presentation.

The news service is the worked example:

```
1 NEWS (home)
  -> 110 NEWS service directory
       -> 111 HACKER NEWS front-page list
            -> 112 STORY detail with one comment
```

- `services/news/service.py` owns the Hacker News URLs, field names, parsing, and
  the cached service. The pages only see `Story` and `Comment` objects.
- `minitel/data/cache.py` starts at most one loader thread per key and never blocks
  the render path. A stale value is kept when a refresh fails, so the terminal
  keeps showing the last good headlines with an `OFFLINE` notice.
- Front-page data is cached for 300 seconds, comments for 1,800 seconds, and a
  failed load is retried after 60 seconds. There are no new dependencies: the
  new modules use only the standard library.
- `minitel/text.py` strips HTML, unescapes entities, transliterates typographic
  punctuation and accents, drops emoji, and wraps to the 40-column screen. Every
  remote title, author, domain, and comment goes through it before `Screen.text`.
- `minitel/design/pager.py` provides the `Pager` used by the four-story list.
- `minitel/data/http.py` provides `get_json()` and `HttpError` for cache threads.
- `pages/common/layout.py` exposes `BODY`, `ACCENT`, `SECONDARY`, and `WARNING`.
  The news pages use yellow story badges, cyan metadata, and magenta warnings;
  on the monochrome M1 these are grey levels.

The weather page is the second cached service:

- `services/weather/service.py` owns the Open-Meteo URL, the four locations
  (`LONDON`, `PARIS`, `LYON`, `MARSEILLE`), WMO code parsing, and one
  `ResourceCache` entry per city. Condition labels live in
  `pages/weather/_support/labels.py`. Data is cached for 600 seconds and failed
  loads retry after 60 seconds.
- `pages/weather/page.py` renders `120` with one row per city: current temperature,
  condition, and today's low/high. It shows `LOADING`, `UNAVAILABLE`, or
  `OFFLINE - CACHED` from the snapshots and ticks every 30 seconds to pick up a
  background load.
- `120#CODE` opens city detail (`120#PAR`, `120#LYO`, and so on). The page
  declares `extension_back_page="120"`, so direct entry returns to the summary
  first, then history. Short city codes live on `Location.code`.
- The page credits `OPEN-METEO`. The source is keyless and uses only the
  standard library, like the news source.
- On `111`, `ctx.set_pager(...)` registers a session-owned cursor. `SUITE`
  advances and wraps; `RETOUR` walks back one page and only leaves the list from
  page 1, the same boundary pattern as multi-field form focus. The cursor is
  remembered per page, so returning to the list resumes the same page.
- `112` declares `back_page="111"`, so typing `112` directly returns to the list
  first, then follows the existing history.

`on_tick` may return a complete `Screen`; the session diffs it against the
shadow screen and restores the input cursor. Raw bytes remain the cheaper choice
for a single changing region.

## Sports and live scores

The football service uses [football-data.org](https://www.football-data.org/) v4.
Put the token in `home_minitel_server/.env`; that file is ignored by Git.

```sh
cp .env.example .env
# edit FOOTBALL_API_KEY=...
```

The loader in `services/common/config.py` reads `.env` from the current directory or
the repository root and never overrides variables already exported in the
shell. The key is never logged or rendered.

```
5 LIVE SCORES (page 150)
  -> 151 MATCH detail
  -> 153 TABLES
  -> 154 FEED STATUS
```

- `pages/sports/live.py` shows one league per page with the league in the title,
  kickoff times as section headers, and two match columns under each time.
  `SUITE` moves through league pages, a 30-second `Carousel` rotates them while
  idle, and numeric selection opens match detail.
- `150#PL` opens the Premier League window directly. `take_extension()` applies
  the league once on entry, so `SUITE` and ticks keep the chosen window.
- If today has no matches, the feed searches the next 20 days in 10-day
  windows (the provider's range limit) and shows the earliest matchday with
  fixtures across the configured leagues. The page becomes
  `NEXT FIXTURES - <league>` and the header shows the date. The extra requests
  are skipped when the quota is nearly exhausted.
- `services/sports/source.py` owns the football-data.org URLs, field names, status
  mapping, team abbreviations, and parsing. Pages only see `Match`, `Team`,
  `Goal`, and `StandingRow`.
- `services/sports/feed.py` owns the only poller. It fetches today's matches for the
  configured competition codes in one request, derives goal/FT/KO/HT alerts, and
  keeps an immutable `FeedSnapshot`. A failed refresh keeps the last good
  snapshot and turns the pages into `DATA STALE` rather than blanking them.
- Polling adapts: 60 s while a match is live, 15 min near kickoff, 30 min when
  idle. `x-requests-available-minute` and `X-RequestCounter-Reset` feed the quota line on
  page 154; the poller slows down if the quota is nearly exhausted.
- Standings are cached per competition for one day and loaded in the background.
- The free football-data.org tier includes the top five leagues and other
  competitions, but its scores are delayed and goal events are not included.
  Live scores require the paid "Free w/ Livescores" plan; goal events require a
  plan with goal scorers. Match detail omits the goals block entirely when the
  provider does not return events, rather than drawing an empty section.

`docs/authoring-pages.md` documents the page contract and the `.env`/service
pattern.

## Screensavers

An idle session can take over the display without navigating away from the
current page. The screensaver preserves history, field values, focus, and pager
offset; any input wakes back to the same page. Idle means no input and no
navigation, so ticking pages still fall asleep.

```sh
uv run python run_server.py --screensaver clock
uv run python run_server.py --screensaver bouncing_ball --screensaver-after 60
uv run python run_server.py --screensaver off
```

`--screensaver` accepts `clock`, `test_card`, `scroll`, `bouncing_ball`,
`carousel`, `all`, or `off`. Screensaver pages declare their group with
`@page(..., screensaver="group")`; `Registry.screensaver_groups()` collects
them. `minitel/` carries a `Screensaver` with a page sequence and a `Carousel`
timing policy, but no specific page numbers. `--screensaver-after` is the idle
delay in seconds; `0` disables automatic activation but leaves manual
activation available. `--screensaver-hold` sets the seconds per page for a
multi-page screensaver.

Page `190` (`7` on the home menu) is the selector. Type `1`-`4` to choose CLOCK,
TEST CARD, BOUNCING BALL, or CAROUSEL, `6` to cycle the auto delay, and `0` to
activate immediately. The screensaver pages are `900` CLOCK, `901` TEST CARD,
`902` SHAKESPEARE (scrolling text), `903` BOUNCING BALL, and the `910`-`912`
CAROUSEL frames.

`MinitelApp(screensaver=..., screensaver_after=..., screensaver_hold=...)`
provides the same configuration for another service. Pages may call
`ctx.set_screensaver(...)` or `ctx.start_screensaver()`.

A content page can also give its pager a carousel policy. The session then
advances the window on idle, resets on input, ignores data ticks, pauses while
a field has text, and suspends during the screensaver. A page that repeatedly
repaints the main content on idle through a carousel may set
`no_screensaver=True`; pages that only update a region should leave the
screensaver enabled so it can prevent burn-in. The Hacker News list and sports
live page are the current carousel callers.

## Terminal power pause

The dongle keeps its TCP connection when the Minitel is switched off, so the
server can otherwise keep writing into a terminal that is not listening. The
session watches the input stream for the terminal's power signals: a `00` byte
when the terminal loses power, and `7c 13 59 13 53 13 54` when it comes back.
The sequences are empirical, not a documented power command; both are
configurable.

While paused, the session stops ticks, screensaver rotation, and carousel
advances, and returns no output. On power-on it resets the parser, restarts the
idle clock, and full-paints the current page (or the active screensaver page),
preserving history, fields, values, focus, and pager offsets. A false off is
recoverable: any later input wakes the session with a full repaint.

The pause is not required to keep the connection or the UART alive. The ESP32's
`writeByte()` does block when its TX FIFO is full, but the server paces below
the serial rate, and the ESP32 drains at the configured baud even when the
Minitel is off. The pause is mainly hygiene: it stops a long page paint from
delaying the power-on bytes, and it stops carousels and the screensaver from
advancing while nobody is looking. If you only want the rewake, use:

```sh
uv run python run_server.py --no-power-pause # ignore off; keep wake repaint
uv run python run_server.py --power-on ""    # keep pause; disable rewake
uv run python run_server.py --no-power       # disable both
```

`--power-off` and `--power-on` take hex byte sequences; an empty value disables
that signal. `MinitelApp(..., power=PowerSignals(off=..., on=...))` provides the
same configuration for another service, including `off=b""` for rewake-only.
Pages need no hook: the mechanism is session-owned, like the screensaver.

## Adding pages

The full guide is in [`docs/authoring-pages.md`](docs/authoring-pages.md).

Short version: create `pages/your_page.py`, use `@page(...)`, return a `Screen`,
and call `page_input(s, ctx)` if you want typing. Restart the server; pages are
discovered automatically. Add a 1-2 digit numeric alias
(`aliases=("6",)`) to put the page on the home menu.

To load pages or services from another package:

```sh
uv run python run_server.py \
  --extra-path ../extra_pages \
  --pages-package extra_pages \
  --services-package extra_services
```

The extra packages are ordinary Python packages and are discovered alongside
the public ones, in the order given. A later package wins a duplicate page
number or alias, with a startup warning; same-package duplicates and duplicate
service keys still abort startup. `--strict-overrides` turns the warning into a
failure. See [Loading another page or service
package](docs/authoring-pages.md#loading-another-page-or-service-package).

## Tools

- `tools/hello.py` - first-light TCP server with terminal probes and key logging.
- `tools/virtual_minitel.py` - decode a Videotex stream into a 25x40 grid.
- `tools/minitel_client.py` - interactive curses terminal client that decodes a
  live server session and sends Minitel keys.
- `tools/sports_probe.py` - fetch today's matches and an optional table through
  the sports source without starting the server; never prints the token.

```sh
uv run python tools/virtual_minitel.py --demo --plain
uv run python tools/virtual_minitel.py --connect 127.0.0.1:3615 --plain
uv run python tools/minitel_client.py --connect 127.0.0.1:3615
```

The interactive client shares the virtual Minitel decoder. `F9` shows the key
map; `Ctrl+Q` quits.

## Scope

- M1: 40 columns, 1200 baud, monochrome, 7E1; the active and only supported
  runtime profile.
- M2: `TerminalProfile` presets are reserved models; detection, speed, colour,
  DRCS, and 80-column mixed mode are not implemented.
- Prestel is a design reference, not a wire profile.

Hardware notes, research, vendored repositories, and personal setup live
outside this repository.

## License

MIT. See [LICENSE](LICENSE).
