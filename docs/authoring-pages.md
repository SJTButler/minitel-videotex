# 11 - Authoring pages: the library API

The server is split into two layers:

```
minitel/     reusable library: codec, screen, render, profiles, page API,
             session, app, transport, text, paging, cache, http, screensaver
pages/       the example service: layout helpers, pages, and data sources
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
@page(number, title="", aliases=(), on_submit=None, on_key=None,
      on_tick=None, tick_interval=None, form=False, on_form=None,
      transient=False, back_page=None, screensaver=None,
      no_screensaver=False, **meta)
def render(ctx):
    return Screen()
```

- `number` is the primary key (`"200"`).
- `aliases` are extra keys (`("4",)` or `("", "0")` for the home page).
- `title` is metadata; it is not drawn automatically.
- `on_submit(ctx, line)` handles `ENVOI`/`Enter` for single-field pages.
- `form=True` and `on_form(ctx, values)` handle multi-field forms; see
  [Multi-field forms](#multi-field-forms).
- `on_key(ctx, key)` handles keys the session does not consume (`GUIDE`,
  arrows, etc.).
- `on_tick(ctx)` and `tick_interval` make the page dynamic; see
  [Dynamic pages](#dynamic-pages).
- `transient=True` keeps the page out of history; see
  [History and transient pages](#history-and-transient-pages).
- `back_page="111"` is the logical `RETOUR` target for direct entry. If history
  does not already point there, `RETOUR` navigates there without pushing the
  current page; the next `RETOUR` follows the saved history.
- `screensaver="group"` declares this page as part of a screensaver sequence;
  see [Screensavers](#screensavers).
- `no_screensaver=True` suppresses automatic screensaver takeover while this
  page is current. Manual activation still works. Use it for pages that already
  change on idle; see [Content carousels](#content-carousels).
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

Every `render`, `on_submit`, `on_form`, and `on_key` receives a
`PageContext`.

| Member | Meaning |
|---|---|
| `ctx.session` | the live `Session` |
| `ctx.profile` | the terminal profile (`M1`, `M2_MONO`, ...) |
| `ctx.registry` | the `Registry` |
| `ctx.line` | the active field's value |
| `ctx.last_key` | the last submitted line (used by the not-found page) |
| `ctx.state` | a per-session dict for page state |
| `ctx.services` | the process-wide injected services |
| `ctx.service(name, default=None)` | look up one service |
| `ctx.active_name` | the active field name, including a pending focus |
| `ctx.values` | all field values for the current page |
| `ctx.fields` | the registered fields |
| `ctx.add_field(name, row, col, width, *, cursor="visible")` | register a named field |
| `ctx.set_input(row, col, width, *, cursor="visible")` | one-field shorthand |
| `ctx.set_pager(total, page_size, *, offset=None, carousel=None)` | register a session-owned pager, optionally with timed advance |
| `ctx.pager` | the `Pager` registered for this render |
| `ctx.focus(name)` | request focus when the page rerenders |
| `ctx.page_for(key)` | look up another page |
| `ctx.screensaver` | the session's `Screensaver`, or `None` |
| `ctx.idle_elapsed` | seconds since the last input or navigation |
| `ctx.set_screensaver(pages, *, after=120, hold=20, wrap=True)` | select the session screensaver |
| `ctx.disable_screensaver()` | remove the session screensaver |
| `ctx.start_screensaver(index=0)` | request an immediate takeover from a handler |

`set_input` is the one-field shorthand; multi-field pages use `add_field`.
Both tell the session where the cursor belongs and what the maximum length is.
The cursor policy is `visible` (the default), `hidden` (never show it), or
`auto` (hide while idle, show while the field is non-empty, and pause ticks
while typing). The inverse field remains the visual target when the cursor is
hidden. `pages.layout.page_input` does both the drawing and the registration:

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
- `footer(s)` writes the default key hints at row 22.
- `key_footer(s, hints, row=22)` joins custom hints with two spaces; pass a
  string or an iterable such as `("SUITE=NEXT", "RETOUR=BACK")`.
- `form_footer(s, ctx, fields)` writes dynamic form key hints at rows 22-23.
- `page_input(s, ctx)` draws `PAGE:` at row 20 and registers the field.
- `BODY`, `ACCENT`, `SECONDARY`, and `WARNING` are semantic colour constants:
  white body, yellow accent, cyan secondary, magenta warning. On the M1 these
  render as grey levels. `ACCENT` is used for the inverse story-number badge.

Use these for consistency. A different service can copy the file or provide its
own layout package and pass its registry to `MinitelApp`.

## Input, submit, navigation

The session handles the common keys:

| Key | Behaviour |
|---|---|
| `ENVOI` / `Enter` | form: `on_form`; single field: `on_submit` |
| `CORRECTION` | remove one character from the active field |
| `ANNULATION` | clear the active field, rerender |
| `SOMMAIRE` | go to `INITIAL`, clear history |
| `SUITE` | form: next field; pager: next page; otherwise page `on_key` |
| `RETOUR` | form: previous field; pager: previous page; otherwise/at the boundary: `back_page` if history isn't already there, then history back |
| `GUIDE` | page's `on_key`, then the app's guide page |

`on_submit` can return:

- a page key (`"110"`),
- a `Page` object,
- `None`, in which case the session looks up the submitted line in the registry.

Example single-field stateful page:

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

`on_key` receives `GUIDE`, `REPETITION`, arrows, and other keys after the
session's built-in handling. Return a key or `Page` to navigate.

## Multi-field forms

A form page declares `form=True`, registers fields with `ctx.add_field`, and
implements `on_form(ctx, values)`:

```python
def submit_form(ctx, values):
    name = values.get("name", "").strip()
    if not name:
        ctx.state["error"] = "NAME REQUIRED"
        ctx.focus("name")
        return "230"
    ctx.values.clear()
    ctx.focus("name")
    return "230"

@page("230", title="FORM", form=True, on_form=submit_form)
def form(ctx):
    s = Screen()
    status(s, "PAGE 230")
    line_field(s, ctx, "name", 3, 6, 20, label="NAME:")
    line_field(s, ctx, "city", 5, 6, 20, label="CITY:")

    error = ctx.state.get("error", "")
    if error:
        s.text(7, 0, error)
    form_footer(s, ctx, [("name", "NAME"), ("city", "CITY")])
    return s
```

with:

```python
from pages.layout import form_footer, line_field, status
```

- `line_field` draws the label, inverse bar, and current value, then registers
  the field. It keeps the draw and registration coordinates in one call.
- For custom drawing, use `ctx.add_field(...)` plus `s.field`/`s.text`
  yourself. Use identical row/column values in both places; a mismatch is the
  usual one-column cursor bug.
- Draw the field bar and its value with the same attributes. The renderer
  leaves the terminal pen set to the cursor cell at the end of a paint, and
  focus moves do the same, so typed text matches the field style. An inverse
  field echoes inverse text; a normal field echoes normal text.
- Separate named fields are better than one combined “handle message” line:
  they keep validation, labels, focus, and `SUITE`/`RETOUR` navigation clear.
- `SUITE`/`RETOUR` re-render the page and send only the changed rows through
  the diff. `form_footer(s, ctx, fields)` uses `ctx.active_name` to show the
  next/previous field, so focus updates the footer without a full repaint.
- `RETOUR` at the first field goes back; `SUITE` at the last field stops.
- `ENVOI` calls `on_form(ctx, values)`. `values` is a snapshot dict;
  `ctx.values` is the live dict.
- On validation failure, set an error, call `ctx.focus(field)`, and return the
  same page. The session rerenders with values and focus preserved.
- On success, clear `ctx.values`, focus the first field, and return the page.
- `on_submit` remains the single-field hook; a one-field form can use it.

## Echo mode

Two models:

- **Local echo** (default): the terminal displays keys as they are pressed; the
  server only updates its line buffer. Instant, zero setup, fewer bytes. But a
  tick can move the cursor while the terminal echoes a key, so on a tick page a
  keypress during the tick can land at the clock. Fine for static pages.
- **Server echo**: the server writes each key at the input cursor. Run with
  `--echo` and the terminal's local echo off. The app serialises ticks and key
  echo, so a character always lands at the field. Recommended for tick pages
  and forms.

To switch:

1. disable local echo in the terminal/dongle settings;
2. start with `uv run python -m minitel.server --port 3615 --echo`;
3. type. Double characters mean local echo is still on. If keys stop reaching
   the server, that setting controlled the key path rather than local echo;
   revert it and keep local echo.

The example defaults to local echo because it requires no terminal setting
change.

## Pagination

Pagination is a session-owned cursor, like form focus. The page declares the
window; the session owns the offset and handles `SUITE`/`RETOUR`:

```python
PAGE_SIZE = 4

@page("111", on_submit=select, on_tick=render_list)
def render_list(ctx):
    items = ...
    pager = ctx.set_pager(len(items), PAGE_SIZE)
    for index, item in enumerate(pager.window(items)):
        ...
    return screen
```

- `ctx.set_pager(total, page_size)` returns a clamped `Pager` using the
  session's current offset. Call it on every render and `on_tick`; pass
  `offset=0` to force the first page after a filter change.
- The session stores the pager. `SUITE` moves to the next page (wrapping from
  the last page to the first); `RETOUR` moves to the previous page and calls
  `back()` only from page 1. Moving pages clears the active input field.
- Do not handle `SUITE`/`RETOUR` in `on_key` on a paginated page; the session
  handles them before `on_key`, just as it handles form focus.
- The offset is remembered per page for the session. Returning from a detail
  page resumes the same list page; each paginated page has its own cursor.
- Page-specific error text is the page's responsibility. If it should disappear
  when the page changes, store the offset with the error and clear it when the
  pager offset differs, as `pages/news/hackernews.py` does.
- Use one cursor style per page: multi-field form focus or a pager, not both.

This is the same shape as multi-field forms: a bounded list, a session-owned
cursor, and a boundary that falls through to history.

## Dynamic pages

A page can update a region without repainting the whole screen. Set
`tick_interval` and provide `on_tick`:

```python
def tick(ctx):
    return codec.pos(3, 7) + codec.text("UPDATED")

@page("150", title="DYNAMIC", tick_interval=1.0, on_tick=tick)
def dynamic(ctx):
    s = Screen()
    status(s, "PAGE 150")
    s.text(1, 0, "DYNAMIC", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "VALUE: UPDATED")
    page_input(s, ctx, cursor="auto")
    footer(s)
    return s
```

- `tick_interval` is in seconds. `None` (the default) means static.
- `MinitelApp` calls `on_tick` while the page is current. Navigating away stops
  ticks; navigating back paints the full page once and resumes.
- Return **only the dynamic region** as raw bytes. The session appends
  `pos(input)` plus the current cursor visibility, so the insertion point
  returns to the `PAGE:` field.
- If a tick moves the cursor, use `page_input(s, ctx, cursor="auto")`. While
  the page is idle the cursor is hidden and ticks run. The first typed
  character sends `CON`, the cursor appears, and ticks pause while the line is
  non-empty. Submit, annulation, or correcting to an empty line sends `COF`
  again and resumes ticks.
- `cursor="hidden"` is also available if a page should never show a cursor.
  `cursor="visible"` with a moving tick will blink or jump: `COF`/`CON` resets
  the terminal’s blink phase, and the tick cannot sync to it.
- Local echo still lands in the inverse field while the cursor is hidden. If
  the terminal’s local echo is off, use `--echo`; the server sends the same
  cursor commands.
- The initial `render` must draw the same region at the same position, so the
  first tick overwrites the same cells.
- A full page is ~240 bytes (~1.8 s at 1200). A small region is ~15 bytes
  (~0.11 s). Do not full-repaint at 1 Hz on the M1.
- If `on_tick` returns a `Screen`, it must be the **complete desired page**;
  the session diffs it against its shadow screen and places the cursor at the
  active input field before diffing. For a single region, return raw bytes
  instead.
- Use a fixed-width value (for example `time.strftime("%H:%M:%S")`) so the
  region never changes length and never needs clearing.

The timer is transport-level: `Session.next_timeout()` says how long to wait,
and `Session.on_timeout()` asks the active page for a tick, activates the
screensaver, or rotates it. `Session.tick()` remains the page-tick entry point.
Input and ticks share one writer, so a page paint is never interleaved with a
tick.

## Screensavers

A screensaver is a session-owned display takeover. It is **not navigation**: the
current page, history, field values, focus, and pager offset are preserved, and
any input wakes back to the page the user was on. The first input chunk is
discarded so a stray `ENVOI` cannot navigate or type into the restored page.

`MinitelApp` configures the default for every new session:

```python
app = MinitelApp(
    registry,
    screensaver=("900",),
    screensaver_after=120.0,
    screensaver_hold=20.0,
)
```

- `screensaver` is a page, a page key, or a sequence of keys/pages.
- `screensaver_after` is the idle delay in seconds. `None` or `0` disables
  automatic activation; manual activation still works.
- `screensaver_hold` is the time each page is held before rotating. `0` keeps
  the first page. The hold lives on a `Carousel` policy; the page sequence is
  organised by a `Pager`.
- The CLI exposes the same settings: `--screensaver`,
  `--screensaver-after`, and `--screensaver-hold`.

Idle means **no input and no navigation**. Page ticks and screensaver repaints
do not count as activity. While a screensaver is active, the underlying page's
ticks stop; only the screensaver page's ticks and rotation run. Activation,
rotation, and wake are full paints, which also avoids stale double-size glyphs
on wake. Screensaver ticks still use the normal diff.

Screensaver pages declare their group on the page itself:

```python
@page("900", title="CLOCK", screensaver="clock")
@page("910", title="KILO", screensaver="carousel")
@page("903", title="BOUNCING BALL", screensaver="bouncing_ball")
```

`Registry.screensaver_groups()` collects pages by that string in page-number
order, and `Registry.screensaver_pages("all")` returns the union. The CLI and
the selector derive their choices from the registry. `pages.DEFAULT_SCREENSAVER`
is the service default. `minitel/` contains no screensaver page numbers.

The timing is separate from the sequence:

- `Pager` is the page cursor. `Screensaver.page(index)` windows the page tuple
  with `Pager(len(pages), 1, index)`.
- `Carousel` is the timed policy: `hold` seconds per page, with `wrap`.
- `Screensaver` holds the pages, the idle `after` delay, and the `Carousel`.

This keeps “when to sleep”, “which pages”, and “when to advance” separate.

A page can select or start a screensaver for its own session:

```python
ctx.set_screensaver(("900", "901"), after=300, hold=20)
ctx.start_screensaver()          # from on_submit/on_key: immediate takeover
ctx.disable_screensaver()
```

`ctx.start_screensaver()` is a request, not a return value: the session applies
it after the handler finishes, so return a page key normally. The selector page
`190` (`7` on the home menu) is the reference implementation. It lets the user
choose `900` CLOCK, `901` TEST CARD, `903` BOUNCING BALL, or `910`-`912`
CAROUSEL, cycle the auto delay, and activate the current choice with `0`.

Rules for screensaver pages:

- They are ordinary `@page` pages; write one file per page and draw the whole
  25x40 screen.
- Do not register input fields; the cursor is hidden. Input wakes instead.
- Use `back_page="190"` so direct entry returns to the selector first.
- Reserve `9xx` for screensaver pages and the promo frames.
- Declare new groups with `@page(..., screensaver="group")`; keep page keys out
  of `minitel/`. Do not use `all` or `off` as group names; they are reserved.
- Keep motion sparse and hold full-screen frames for several seconds; the M1
  budget is 133 cps.
- A page that is itself in the screensaver set does not auto-activate.
- `ctx.idle_elapsed` is available if a page wants to change after a long idle.

Mechanism tests use a fake clock and call `next_timeout()`/`on_timeout()`
directly; page tests assert layout and the ball's bounds. No sleeps are needed.

## Content carousels

A page can give its content pager a timed advance policy. It is the same
`Carousel` value the screensaver uses, attached to the page's `Pager` rather than
a takeover. `Carousel` is exported from `minitel`.

- The page registers the pager with a carousel hold and wrap flag.
- The session owns the deadline and advances the pager when the page is current,
  the field is empty, and the screensaver is not active.
- Input and navigation reset the interval. Page ticks do **not**.
- Any non-empty field pauses the carousel, so a list cannot move under a
  half-typed selection.
- Fewer than two pages means no advancement. With `wrap=False`, the carousel
  stops at the last page.
- Auto-advance updates the remembered pager offset and re-renders with the normal
  diff. It does not navigate, push history, or call the submit handler.
- The screensaver suspends the content carousel; wake or return starts a fresh
  hold.
- A data refresh that changes the total does not reset an unchanged page
  position. Going from no pages to pages starts a fresh hold.

A page that changes on idle will usually also set `no_screensaver=True`. That
keeps the automatic screensaver from interrupting the content carousel; manual
activation through the selector still works.

If a page has several ways to register its pager (normal render, `on_tick`, and
`on_submit`), declare the carousel in one helper and use that helper everywhere.
Otherwise the session sees a different declaration and restarts the interval.
This is also why the data tick must re-register the same pager with the same
policy.

The Hacker News list is not converted yet. Converting it means choosing a hold,
declaring the same policy wherever the list registers its pager, adding
`no_screensaver=True`, and leaving the two-second data tick in place. All of the
timing remains in the session; the page gains no timer code.

## Partial updates

The session keeps a shadow `Screen`. `Session.refresh()` re-renders the current
page and returns `Action(raw=render_diff(old, new))`. `ANNULATION` uses it, and
a `Screen` returned by `on_tick` is diffed. `render_diff` repaints **whole
changed rows**, not individual cells:

- a footer row is ~40 bytes;
- a clock row is ~15 bytes;
- an unchanged page produces no bytes.

Raw tick frames bypass the shadow screen. A later `refresh()` may repaint rows
that changed through raw frames; that is correct but less efficient. Use one
mode per page when it matters.

Form focus uses `refresh()` and the diff, so a footer built from
`ctx.active_name` updates automatically. Only the footer rows and cursor are
sent.

## Live data and services

Keep network calls out of `render`, `on_submit`, `on_key`, and `on_tick`. Fetch
in a background thread, cache the result, and render from the cache. The app
injects services once and each session gets a copy:

```python
app = MinitelApp(
    registry,
    initial="100",
    fallback=registry.get("__not_found__"),
    services=pages.build_services(),
)
```

A service is any object. If it has `start()` or `stop()`, `MinitelApp.serve()`
calls them before listening and in a `finally` block. A hook may be a normal
function or a coroutine. Pages read services with `ctx.services` or
`ctx.service("hackernews")`.

The library pieces:

- `minitel/cache.py` - `ResourceCache.get(key, loader)` returns a `Snapshot`
  immediately and starts at most one daemon loader per key. A `Snapshot` has
  `value`, `loaded_at`, `error`, `loading`, `has_value`, and `age()`. On a failed
  refresh the old value is kept and `error` is set. `load_now()` is synchronous
  and exists for tests and prewarming; `retry()` clears a failed-load backoff
  and triggers a fresh load. Inject `clock` and `thread_factory` for
  deterministic tests.
- `minitel/http.py` - `get_json(url, headers=None, timeout=10.0)` raises
  `HttpError` with `status`, `body`, and `retry_after`.
- `minitel/text.py` - `plain`, `sanitize`, `fit`, `wrap`, `domain`, and `age`.
  Remote text is not guaranteed to be encodable: HTML tags, entities, curly
  quotes, emoji, and non-Latin scripts will crash the renderer if passed
  straight to `Screen.text`. Run every fetched title, author, domain, and
  comment through `sanitize` first.
- `minitel/paging.py` - a frozen `Pager(total, page_size, offset)` with
  `clamp()`, `window()`, `next(wrap=True)`, `prev(wrap=True)`, and `label`.

The news example is split along the same lines:

- `pages/news/directory.py` renders `110`, a data-driven directory. `NEWS_SERVICES` is the
  extension point; a matching number opens its page, and other numbers fall
  through to normal registry routing.
- `pages/news/hackernews.py` renders `111` (four stories with a blank separator row,
  `1`-`4` + `ENVOI` selects) and `112` (metadata first, comment on a later
  tick). `111` registers its window with `ctx.set_pager`, so the session handles
  `SUITE`/`RETOUR`; `RETOUR` walks back through pages and only leaves from page
  1. `112` declares `back_page="111"`, so typing `112` directly returns to the
  list first, then follows the existing history. A selected `Story` is kept in
  `ctx.state["news_story"]`; direct access to `112` shows `NO STORY SELECTED`.
- `pages/news/source.py` owns the Hacker News URLs and field names, parses
  `Story`/`Comment` objects, and wraps one `ResourceCache` for the front page
  and one for comments. The cache does not block a page paint; the first paint
  shows `LOADING` and a later tick shows the data.

The weather page is a second, deliberately different cached source:

- `pages/weather/source.py` owns the Open-Meteo URL, the location table, WMO
  condition labels, and one cache entry per city. Each city is a separate key,
  so one failed location does not hide the others.
- `pages/weather/page.py` renders one row per city with current temperature,
  condition, and today's low/high. It derives `LOADING`, `UNAVAILABLE`, and
  `OFFLINE - CACHED` from the snapshots and ticks every 30 seconds to pick up
  background loads.
- The page credits Open-Meteo. The source is keyless and uses only the standard
  library.

A page that returns a complete `Screen` from `on_tick` gets the same cursor
restoration as a normal render. That is what makes a list or detail page usable
with the `PAGE:` field still active.

## History and transient pages

`SOMMAIRE` clears history; `RETOUR` pops it. A page declared `transient=True`
is **not pushed** when you leave it. If you return to the page that launched
it, that history entry is popped as well, so a form step does not leave a loop
in history.

Use transient pages for multi-step form flows, confirmations, login steps, and
one-shot screens. A transient step is not pushed when you leave it; if you
return to the page that launched it, that entry is popped. The guestbook is now
a single form page, so it no longer needs a transient step; the capability
remains for multi-page flows.

Field focus (`SUITE`/`RETOUR` inside a form) never modifies history. Only an
actual page navigation pushes or pops the history stack.

A page may declare a logical parent with `back_page="111"`. This is used when
the page was reached directly (for example by typing `112`) and history does
not already point at `111`: `RETOUR` navigates to `111` without pushing `112`,
and the next `RETOUR` follows the history that was already there. If history
already points at the parent, `RETOUR` pops it normally. The rule applies to
plain pages, the first field of a form, and page 1 of a pager.

Normal pages are pushed as usual.

## Aliases and the menu

`@page("110", aliases=("1",))` lets the user type either `1` or `110`. The home
page uses `aliases=("", "0")`, so an empty submit and `0` both go home.

Keep page numbers stable and descriptive. The example scheme is:

| Number | Page |
|---|---|
| `100` | home / index |
| `110` | news service directory |
| `111` | Hacker News headline list |
| `112` | story detail |
| `120` | weather: current conditions and today's forecast |
| `130` | about / guide |
| `140` | guestbook |
| `190` | screensaver selector (`7` on the home menu) |
| `900` | CLOCK screensaver |
| `901` | TEST CARD screensaver |
| `903` | BOUNCING BALL screensaver |
| `910`-`912` | CAROUSEL promo frames |
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
- Call page_input(s, ctx) for a single field, or ctx.add_field(...) and
  form=True/on_form(ctx, values) for a multi-field form.
- Use ctx.state for per-session data.
- Add a menu line in pages/home.py.
- Run: uv run python -m unittest discover -s tests -v
- Inspect: uv run python tools/virtual_minitel.py --connect 127.0.0.1:43620 --plain
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
- **Background services**: injection, `ctx.services`, and `start()`/`stop()`
  hooks are implemented. The news source is the reference for a cached live
  feed. A shared scheduler, a multi-user hub, and push updates are still future
  work above `Session`.
- **Forms**: multi-field focus and `on_form` are implemented. Field masks,
  validators, and cursor/insert editing are natural extensions of `Session`.
- **Themes**: copy `pages/layout.py` or create another layout package. The core
  renderer does not contain the `3615 KILO` status bar.

## Rules of thumb

- 40 columns, 24 content rows. Row 0 is the terminal's status area.
- One idea per page.
- Use inverse and double width for hierarchy, not decoration.
- Use `ACCENT` for numbers/actions, `SECONDARY` for metadata/hints, and
  `WARNING` for errors; on mono these are grey levels.
- Keep the `PAGE:` field at row 20 and the footer at row 22.
- Page copy is English. Only the Minitel key names (`ENVOI`, `RETOUR`,
  `SUITE`, `SOMMAIRE`, `GUIDE`, `CORRECTION`, `ANNULATION`) stay French.
- Design uppercase-first; accents cost three bytes each.
- Sanitize remote text with `minitel.text.sanitize` and wrap it with
  `minitel.text.wrap` before drawing.
- Prefer `REP`-friendly runs (the renderer already compresses runs of 3+).
- Test on the M1 and with the virtual Minitel.
- Screensaver pages draw the full screen, hide the cursor, and keep motion
  sparse; do not give them a `PAGE:` field.
- Content carousels are declared on the pager, not implemented with page-local
  timers. Pages that change on idle should usually set `no_screensaver=True`.
- Keep `minitel/` free of application content; keep `pages/` free of protocol
  byte wrangling.
