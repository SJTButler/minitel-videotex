# 11 - Authoring pages: the library API

The server is split into three layers:

```
minitel/     reusable library: codec, screen, render, profiles, page API,
             session, app, transport, text, paging, cache, http,
             services, screensaver
services/    background services: provider adapters, caches, pollers, config
pages/       presentation: layout helpers and pages
tests/       library, service, and page tests
tools/       server probes, virtual Minitel decoder, interactive client
```

`minitel/` has no knowledge of `services/` or `pages/`; `services/` may import
`minitel/` but never `pages/`. You can point `MinitelApp` at any registry, which
makes it usable as a library rather than a single application.

## Quick start: add a page

Create `pages/hello.py`:

```python
from datetime import datetime

from minitel import Screen, codec, page

from pages.common.layout import footer
from pages.common.widgets import page_input


@page("200", title="HELLO")
def hello(ctx):
    s = Screen()
    ctx.set_status("PAGE 200")
    s.text(1, 0, "HELLO", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "THIS PAGE WAS ADDED IN ONE FILE.")
    s.text(5, 0, datetime.now().strftime("TIME: %H:%M:%S"))
    page_input(s, ctx)
    footer(s)
    return s
```

Restart the server. The page is auto-discovered; type `200` in the `PAGE:`
field and press `ENVOI`.

To put it on the main menu, give it a 1-2 digit numeric alias:

```python
@page("200", title="HELLO", aliases=("6",))
```

The home page builds its menu from those aliases; do not edit `pages/home.py`
to add an entry. See [Aliases and the menu](#aliases-and-the-menu).

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
      transient=False, back_page=None, extension_back_page=None,
      screensaver=None, no_screensaver=False, scroll=False, paint=None,
      requires=(), extensions=False, header=None, announce=None,
      announce_channel=None, **meta)
def render(ctx):
    return Screen()
```

- `number` is the primary key (`"200"`).
- `aliases` are extra keys (`("4",)` or `("", "0")` for the home page). A
  1-2 digit numeric alias also declares a home-menu entry; see
  [Aliases and the menu](#aliases-and-the-menu).
- `requires=("sports",)` declares the process-wide services the page needs; the
  server validates the graph at startup.
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
  page is current. Manual activation still works. Use it only for pages that
  repeatedly repaint the main content on idle, such as a carousel; a page that
  only updates one region should leave the screensaver enabled to prevent
  burn-in. See [Content carousels](#content-carousels).
- `scroll=True` lets the page use the terminal's hardware scroll mode
  ("mode rouleau"). Rows 1-24 scroll; row 0 is fixed. The page must return a
  complete `Screen` from `render`/`on_tick`; the session owns the mode and the
  renderer turns a one-row shift into `LF` plus a small repaint. See
  [Scrolling text pages](#scrolling-text-pages).
- `paint` selects the update strategy: `None`/`"row"` (default) repaints
  changed rows, `"cell"` writes only changed cell runs, and `"full"` full-paints
  every update. A `Screen` can override it for one frame. See
  [Update paint modes](#update-paint-modes).
- `extensions=True` lets the page be addressed as `number#token`, such as
  `120#PAR`; see [Page extension codes](#page-extension-codes).
- `extension_back_page="120"` sets the logical `RETOUR` parent for extension
  routes. The default `None` follows history; the base page is not
  automatically the parent. Use it only for a genuine summary/detail pair;
  sibling pages such as `153` and `150` should leave it unset and follow
  history.
- `header=None` uses the app header. `header=False` means this page owns row 0.
  A `Header` instance selects a page-specific header. See
  [Headers](#headers).
- `announce=provider` declares a per-session announcement source;
  `announce_channel` names the channel (default: the page number). See
  [Announcements](#announcements).
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
| `ctx.profile` | the active terminal profile; the server currently runs `M1` |
| `ctx.registry` | the `Registry` |
| `ctx.extension` | the route token for `number#token`, or `None` on the base page |
| `ctx.line` | the active field's value |
| `ctx.last_key` | the last submitted line (used by the not-found page) |
| `ctx.state` | a per-session dict for page state |
| `ctx.service(name, default=None)` | look up a service declared in `requires` |
| `ctx.add_resource(resource)` | register a per-session object to close on disconnect |
| `ctx.active_name` | the active field name, including a pending focus |
| `ctx.values` | all field values for the current page |
| `ctx.input_value` | the value of the `PAGE:` field |
| `ctx.clear_input()` | clear the `PAGE:` field |
| `ctx.set_status(text)` | declare the row-0 status label for the default header |
| `ctx.fields` | the registered fields |
| `ctx.add_field(name, row, col, width, *, cursor="visible", live=False, visible=True)` | register a named field |
| `ctx.set_input(row, col, width, *, cursor="visible", live=False, visible=True)` | one-field shorthand |
| `ctx.set_pager(total, page_size, *, offset=None, carousel=None)` | register a session-owned pager, optionally with timed advance |
| `ctx.pager` | the `Pager` registered for this render |
| `ctx.set_choice(total, page_size, *, selected=None, reset=False, wrap=False)` | register a selectable paged list |
| `ctx.choice` | the active `Choice` for this render, or `None` |
| `ctx.set_viewport(total, height, *, offset=None, follow=None, step=None)` | register a session-owned viewport over a line buffer |
| `ctx.viewport` | the active `Viewport` for this render, or `None` before the page sets one |
| `ctx.set_stops(stops, *, start_next=0, start_prev=0, selected=None, reset=False, wrap=True)` | register viewport match stops |
| `ctx.stops` | the active `Stops` for this render, or `None` |
| `ctx.focus(name)` | request focus when the page rerenders |
| `ctx.page_for(key)` | look up another page |
| `ctx.screensaver` | the session's `Screensaver`, or `None` |
| `ctx.idle_elapsed` | seconds since the last input or navigation |
| `ctx.set_screensaver(pages, *, after=120, hold=20, wrap=True)` | select the session screensaver |
| `ctx.disable_screensaver()` | remove the session screensaver |
| `ctx.start_screensaver(index=0)` | request an immediate takeover from a handler |

`set_input` is the one-field shorthand; multi-field pages use `add_field`.
Fields tell the session where the cursor belongs and what the maximum length is.
The cursor policy is `visible` (the default), `hidden` (never show it), or
`auto` (hide while idle, show while the field is non-empty, and pause ticks
while typing). The inverse field remains the visual target when the cursor is
hidden. `pages.common.widgets.page_input` does both the drawing and the
registration:

```python
page_input(s, ctx)
```

A field can also be `live` and/or hidden:

- `live=True` re-renders the page after every edit, correction, and
  cancellation. The page must be cheap: cache immutable lines and recompute
  only the derived match state. A live field is not cleared by `SUITE`/`RETOUR`
  cursor movement; `ANNULATION` still clears it.
- `visible=False` captures text without drawing a field bar or cursor. The page
  must draw the buffer itself (the reader uses row 0); hidden fields assume
  server echo, the default. `--local-echo` would print the characters at the
  terminal cursor, so use a visible field there.
- The field width is always the buffer cap, not necessarily the display width.
  A hidden reader field can hold 32 characters and show a shorter status window.

Without an input field, typing returns `BEL` and the cursor is parked at row
24, column 0.

## Headers

A header is a row-0 view composed with the body page. It is not a page: it has
no number, alias, history, fields, or navigation. The app selects one header
and the session schedules its ticks and composes only its row 0 over the body.

```python
from minitel import Header, Screen

class MyHeader(Header):
    tick_interval = 1.0
    requires = ("clock",)

    def render(self, ctx):
        screen = Screen()
        screen.fill(0, 0, 40, " ", inverse=True)
        screen.text(0, 0, ctx.service("clock").label, inverse=True)
        return screen
```

- `render(ctx)` returns a `Screen` whose row 0 is used, or `None` to leave the
  body's row 0 untouched.
- `tick_interval` is a positive number of seconds or `None`. The session
  schedules the tick; the header does not own a timer.
- `requires` declares services the header needs. They are validated with the
  page graph and included in the orphan-service report.
- `paint` is the row-0 update strategy: `None`/`"row"` (default) or `"cell"`.
  `"full"` is rejected because a header owns only row 0. A returned `Screen` can
  set `screen.paint` to override the class value for that frame; `None` keeps
  the row redraw. See [Update paint modes](#update-paint-modes).
- Header instances are shared across sessions. Keep them stateless; put
  per-session state in `ctx.state`.
- A header cannot navigate, submit, or receive keys. Those belong to pages and
  the session.

`HeaderContext`:

| Member | Meaning |
|---|---|
| `ctx.body_page` | the current body page or extension page |
| `ctx.body_row` | the body's last rendered row 0 as a tuple of cells |
| `ctx.status_text` | the declared page status, or `None` |
| `ctx.screensaver_active` | true while the screensaver owns the display |
| `ctx.state` | the per-session state dict |
| `ctx.profile` | the active terminal profile |
| `ctx.service(name, default=None)` | look up a service declared by the page or header |
| `ctx.now` | wall-clock seconds |

Select the header at app construction:

```python
app = MinitelApp(registry, initial="100", header=MyHeader(), ...)
```

`run_server.py` uses `pages.HEADER` when the page package defines it.

Pages declare the status label for the default header:

```python
ctx.set_status("PAGE 140")
```

`StatusHeader` renders it with `pages.common.layout.status`. If a page declares
no status, the default header preserves a page-painted body row; if the body
row is blank it falls back to `PAGE <number>`. It passes the screensaver row
through unchanged.

A page can override the app header:

```python
@page("990", header=False)
def full_screen(ctx):
    ...
```

- `header=None` (default) uses the app header.
- `header=False` means the page owns row 0; no header is composed.
- `header=MyHeader()` uses that header for this page only.
- `ExtensionPage` inherits the base page's header.

The optional `ChyronHeader` in `pages/common/header.py` is a user-space
presentation example: it inherits the status behaviour, but when an
announcement is current it draws a right-to-left ticker using
`ctx.announcement_elapsed`. The ticker frame sets `screen.paint = "cell"`, so a
one-frame move does not clear the inverse row; its idle status fallback leaves
`paint` unset and keeps the row redraw. Select it with `--chyron`. Its
conservative defaults are a 1.0 s frame and two columns per frame; tune
`tick_interval` and `step_columns` with a hardware pacing check. Long text gets
a longer display time, clamped by `AnnouncementPolicy.max_duration`. The ticker
stops at column 35 and reserves the last four columns for the terminal `F/C`
indicator and right margin. A page-specific header still wins, so the reader's
`AnnouncementHeader` is not replaced by `--chyron`.

`StatusHeader` and `AnnouncementHeader` deliberately keep row paint. The
full-row redraw, including the black-to-inverse flash, is the visible change
cue for a status or a static announcement; only the animated chyron ticker and
page-owned rows opt into cell paint.

Use per-page overrides sparingly: a full-screen page, a test card, or a page
with a bespoke status row. The app header should cover the normal case.

## Announcements

A page can declare a source of session announcements:

```python
from minitel import Announcement

def goal_alerts(ctx):
    feed = ctx.service("sports")
    if feed is None or not feed.configured:
        return ()
    snapshot = feed.snapshot()
    return tuple(
        Announcement(
            key=("goal", alert.match_id, alert.kind, alert.minute),
            text=f"GOAL {alert.home} {alert.home_goals}-{alert.away_goals} "
                 f"{alert.away}",
            at=alert.at.timestamp(),
        )
        for alert in snapshot.alerts
        if alert.kind == "GOAL"
    )

@page(
    "150",
    title="LIVE SCORES",
    requires=("sports",),
    announce=goal_alerts,
    announce_channel="sports",
)
def live_scores(ctx):
    ...
```

- The provider receives `AnnounceContext`: `page`, `state`, `now`, and
  `service(name)` for services declared in `requires`.
- It is synchronous, read-only, non-blocking, and does no network I/O. The
  session calls it per connection on its announcement poll (default 5 s); keep
  the derivation cheap. The shared service owns the expensive fetch and cache.
- `key` must be stable across polls, because it is the dedupe identity.
  `text` is sanitized by the session; the active header decides truncation,
  wrapping, or scrolling. `at` is optional Unix-epoch seconds and should be set
  by sources that can backfill. `duration` is optional.
- `announce_channel` defaults to the page number. The composed registry keeps
  one active source per channel: a later package can replace the source
  without replacing the page, with a startup report and
  `--strict-overrides`. Same-package duplicate channels are fatal.
- The provider runs even when its page is not current, so a source can
  announce on any page. A page can declare one provider.
- New announcements are queued per session and the active header renders the
  current one on row 0. The default policy shows for 12 s, waits 4 s, and
  queues up to 8; a header may override the display time. The page status or a
  page-owned row returns after the announcement hides.
- A page with its own row 0 uses `AnnouncementHeader` (announcements only,
  otherwise pass through). The reader `160` does this. `header=False` opts out
  of both status and announcements.
- `--no-announcements` disables polling and display;
  `--no-announcements-on-screensaver` keeps the screensaver row alone.
- The server log records a caller only when a poll produces newly seen
  announcements, for example `ANNOUNCE sports <- 150: 2 new`. It shows the
  caller and new count, never the announcement text. The first poll seeds
  existing history without logging, and backfilled timestamps do not count as
  new. Show and hide also log the caller. Provider errors are logged with the
  caller and exception.
- Page `985` in the optional `diagnostics_pages` package is a deterministic
  test source: load the package, open `985`, set `MODE` to `ON`, then navigate
  anywhere. It emits a test announcement every 15 seconds without a live feed.

## Session resources

A service is process-wide and discovered by the server. A **session resource**
is per-connection: a store, connection, or other object that a page creates for
one connected terminal and that must be cleaned up when that connection ends.

```python
store = GuestbookStore()
ctx.add_resource(store)
ctx.state["guestbook_store"] = store
```

`Session.close()` calls each registered resource's `close()` once, in reverse
registration order, and `MinitelApp.handle()` calls it when the connection
ends, including on error. Resource close errors are logged by the app and do not
prevent the other resources from closing.

Use `ctx.add_resource` for stores and connection-scoped handles. Do not register
a process-wide service; the app owns service lifecycle. Do not add a resource
after the session has closed.

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

For raw protocol work, `minitel.protocol.codec` exposes `pos`, `home`, `clear`, `fg`,
`bg`, `inverse`, `flash`, `underline`, `size`, `repeat`, `mosaic`, `cursor`,
and the input parser. Most pages should not need it beyond constants.

Presentation hints on a `Screen`:

| Attribute | Meaning |
|---|---|
| `screen.paint` | per-frame update mode: `None`, `"row"`, `"cell"`, or `"full"` |
| `screen.paint_order` | `"down"` (default) or `"up"` for the first full paint |
| `screen.force_full` | force this update to be a full paint |

Use `screen.paint` to choose cell paint for one frame, or `"full"` to force a
single full paint. A page declaration is usually better for a stable policy;
see [Update paint modes](#update-paint-modes).

## Layout helpers

`pages/common/` is the shared presentation tier. Feature-private helpers live
under `pages/<feature>/_support/`; the top level of each feature contains only
page modules. The shared theme is:

- `ctx.set_status("PAGE 200")` declares the top-row label; the app header
  (`pages.HEADER` / `StatusHeader`) paints the full inverse top row and keeps
  the page number clear of the terminal's `F/C` indicator. Pages should not
  paint row 0 themselves. `status(s, text)` remains the shared row renderer for
  a page that opts out with `header=False`.
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
| `SUITE` | form: next field; choice: next item; pager: next page; viewport with 2+ stops: next match; otherwise page `on_key` |
| `RETOUR` | form: previous field; choice: previous item (at the first item: history); pager: previous page; viewport with 2+ stops: previous match; otherwise/at the boundary: `back_page` if history isn't already there, then history back |
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
    ctx.set_status("PAGE 220")
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
    ctx.set_status("PAGE 230")
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
from pages.common.widgets import form_footer, line_field
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

- **Server echo** (default): the server sends local echo off, writes each key at
  the input cursor, and serialises ticks with key echo. A character always lands
  at the field. Recommended for tick pages and forms.
- **Local echo**: the terminal displays keys as it is pressed; the server only
  updates its line buffer. Instant, fewer bytes, but a tick can move the cursor
  while the terminal echoes a key, so on a tick page a keypress during the tick
  can land at the clock. Fine for static pages. Run with `--local-echo`.

The server asserts the terminal's echo mode itself: server echo sends local echo
off, and `--local-echo` sends local echo on. It does this on every new connection
and again on power-on, so a Minitel power cycle no longer leaves the terminal in
the wrong mode. The dongle's own `Echo` preference is only the initial/pre-
connect state; the server's echo contract wins for the session.

If keys stop reaching the server after the override, the terminal's switch
matrix is the wrong one for this path; report the unit rather than adding page
code.

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
  `back()` only from page 1. Moving pages clears the active input field unless
  the field is live.
- For a **selectable** list, use `ctx.set_choice(total, page_size)` instead of
  a pager. The `Choice` owns both the selected item and the outer page.
  `SUITE`/`RETOUR` move the selection through all items; when the selection
  crosses a page boundary the outer page follows. The first item is selected
  when the list appears; `RETOUR` at the first item follows history and `SUITE`
  at the last clamps. `ENVOI` reaches `on_submit`, where the page reads
  `ctx.choice.selected` and opens that item. Do not mix a choice with a pager or
  viewport.
- Do not handle `SUITE`/`RETOUR` in `on_key` on a paginated page; the session
  handles them before `on_key`, just as it handles form focus.
- The offset is remembered per page for the session. Returning from a detail
  page resumes the same list page; each paginated page has its own cursor.
- Page-specific error text is the page's responsibility. If it should disappear
  when the page changes, store the offset with the error and clear it when the
  pager offset differs, as `pages/news/hackernews.py` does.
- Use one cursor style per page: multi-field form focus, a pager, or a viewport,
  not more than one.

## Scroll viewports

A page with `scroll=True` can register a session-owned viewport over its line
buffer. The page owns the lines and the layout; the session owns the offset,
follow state, and key handling.

```python
@page("155", title="VIDIPRINTER", scroll=True, on_tick=render_feed,
      tick_interval=5.0)
def render_feed(ctx):
    lines = tuple(alert_text(alert) for alert in alerts)
    viewport = ctx.set_viewport(len(lines), 24, follow=True)
    screen = Screen()
    for index, line in enumerate(viewport.window(lines)):
        screen.text(1 + index, 0, fit(line, 39))
    return screen
```

- `ctx.set_viewport(total, height)` returns a clamped `Viewport`. Call it on
  every render and tick. `offset=None` uses the active cursor, then the offset
  remembered for this page key, then `0`.
- `follow=None` preserves the current follow state. Pass `follow=True` when the
  page should start at the tail; pass it only on entry, not on every tick, or
  the user's freeze will be undone. `Viewport.page_down` resumes follow when it
  reaches the bottom.
- `UP`/`DOWN` always move one line. `SUITE`/`RETOUR` move by `step` lines;
  `step=1` (the default) is the M1-friendly one-line move that uses the
  one-line `LF`/`VT` fast path. `step=8` is the largest step that stays on the
  fast path; larger steps fall back to a changed-row repaint. `RETOUR` at the
  top follows `back_page`/history; `SUITE` at the bottom resumes follow.
- The viewport is remembered per page key. A static reader can restore its
  position; a live feed can request the tail on entry.
- `viewport.line_number`, `viewport.total`, `viewport.height`, and
  `viewport.offset` are available for a header or position label.
- Only row 0 is hardware-fixed. A footer below it scrolls unless repainted after
  every scroll, which costs bytes; use row 0 for static chrome.
- A scroll page may have one input field, but not a multi-field form or a pager.
- Do not send `LF`, `VT`, or scroll-mode bytes from a page.

### Viewport stops

A viewport may declare **stops** for selecting matching links. A `Stop` is one
per matching target, with the target's first line (stable order), a reveal line
(the topmost visible occurrence, or the first line), and the link index. The
page builds `(Stop, ...)` and calls:

```python
stops = ctx.set_stops(
    stops,
    start_next=start_next,
    start_prev=start_prev,
    reset=buffer_changed,
)
selected = stops.selected_stop
```

- The session owns the selected stop and the viewport offset; the page owns the
  stop list and drawing.
- With two or more stops, `SUITE`/`RETOUR` cycle all matching targets. The first
  press selects `start_next`/`start_prev`; later presses move and wrap, and the
  session reveals the selected line with a minimal scroll.
- `start_next`/`start_prev` are the topmost visible target when one is visible;
  otherwise the first target below / last target above the window. Compute them
  from the current `viewport.window`.
- `reset=True` clears the selection when the find buffer changes;
  `selected=None` preserves it while the target list is unchanged (for ticks
  and reveals).
- Stops are viewport metadata, not a second cursor. The page still declares one
  viewport and at most one field; `ENVOI` is the page's `on_submit`, using
  `ctx.stops.selected_stop` or the single visible match.
- Reader colour is link-only. Link anchors use `SECONDARY` at rest, `WARNING`
  for matched non-selected targets, and inverse for the selected target (or the
  sole visible target). Headings use inverse; titles, the status row, and the
  field use inverse; quote, code, rule, credit, pager, query, status, tags, and
  snippets stay normal. An index result title is a link and may use the link
  colour; the rest of the result stays normal. The selected target is the only
  link `ENVOI` follows when a selection exists.
- Do not use inline underline for links on the M1. The underline runs from the
  trigger space to the row end and `underline(False)` does not retract an
  already-drawn row. Reserve underline for whole-line headings/metadata.
- For whole-line underline, `paint_runs` closes each underlined run with
  `underline(False)` and `diff_row_bytes` repaints the whole row (including
  blank default cells) when either the old or new row contains underline; the
  full paint after wake is the reference. The virtual decoder models per-cell
  underline and cannot see the row effect, so attribute changes need a hardware
  check.

### Reader documents

`services/common/reader.py` defines the content-free reader model: `Span`,
`Block`, `Link`, `Document`, `SearchResult`, `ReaderSource`, the cached
`ReaderService`, the synchronous `StaticReaderService`, and `find_links` /
`match_prefix`. A source owns sanitising and stable link tokens.

`pages/common/reader.py` owns the shared presentation: `render_lines`,
`visible_matches`, `build_stops`, `starts_for`, `find_results`,
`article_screen`, and `index_screen`. Page `160 WIKIPEDIA` is the first caller;
it serves the live `services/wikipedia/` source through the `wikipedia` service
key. `services/wikipedia/source.py` calls the MediaWiki action API, resolves
internal link titles in batches, and encodes pageids as base36 tokens;
`services/wikipedia/html.py` parses the action HTML into reader blocks. The page
tests inject `tests/fixtures/wikipedia.py` with a `StaticReaderService`; that
fixture is not a production service.

The reader index is a live search command plus a `Choice`: typing a new query
and pressing `ENVOI` searches; pressing `ENVOI` with the unchanged query opens
the selected result. An empty buffer with a current result selection also opens
the selected result; an empty query with no results is a prompt. `SUITE`/`RETOUR`
move the result selection and the outer page follows at the boundary. Returning
via `GUIDE` or history restores the last query and result selection. The selected
result title is inverse; the other result titles use the link colour; tags and
snippets stay normal.

`article_screen` sets `screen.paint = "cell"` so find highlighting and the
selected-link inverse update without clearing each link row. The index stays on
row paint, where its double-size title and selected result are a useful
full-row change cue. The article remains `scroll=True`; a scroll that also
restyles links uses the renderer's style-change shift path. Article links use
colour and inverse, never underline, so they do not hit the underline barrier.

Headings are flush left in v1; `Block.level` is carried for a later hierarchy
rule. If indentation is added, use h2 flush, h3 +2 columns, and h4 +4 columns.
Links match both their visible anchor labels and the target title, so a source
must populate `Link.labels` from the anchors it emits.

This is the same shape as multi-field forms: a bounded list, a session-owned
cursor, and a boundary that falls through to history.

## First paint order

A page that appends the newest lines at the bottom can paint the first full
screen bottom-up:

```python
screen.paint_order = "up"
```

The renderer still paints row 0 first, then rows 24 down to 1. This makes the
newest bottom line appear first on a full paint. It does not change the model
or diffs: appended lines are still bottom updates, and later one-line changes
use the normal diff. The default is `"down"`.

If a page first shows a loading or empty state and later gets its data, set
`screen.force_full = True` on that first data render. The session sends a full
paint instead of a diff, so the `paint_order` choice applies to the transition:

```python
if has_events and not ctx.state.get("loaded"):
    ctx.state["loaded"] = True
    screen.force_full = True
```

`screen.force_full` is a one-shot choice. A page that declares
`paint="full"` chooses a full paint for every update instead; that is usually
too expensive for a 1 Hz page. `paint_order` applies to either full-paint path.

## Update paint modes

A page or header declares how its updates are painted:

| Mode | Behaviour |
|---|---|
| `"full"` | every update is a full-screen paint |
| `"row"` | repaint changed rows (the default; `None` means row) |
| `"cell"` | write only changed cell runs; do not clear the row first |

```python
@page("150", title="LIVE", tick_interval=5.0, on_tick=live_tick,
      paint="cell")
def live(ctx):
    return live_screen(ctx)
```

Cell paint is for small, frequent changes: a clock digit, a score, a moved
ball, or a link highlight. It groups adjacent changed cells with the same
attributes into runs and preserves unchanged cells and their attributes. It
uses `CAN` only for a trailing default region; an inverse or coloured tail is
written as runs. It never clears a whole row just to change one cell.

The mode is a declaration, not a page-local renderer:

- The page declaration is the default for body rows 1-24. `screen.paint` on the
  returned `Screen` overrides it for that frame.
- A header declaration applies to row 0 only. A header result `Screen.paint`
  overrides the header's class value for that frame. Headers cannot declare
  `"full"`.
- If the header passes through (`render` returns `None`) or the page declares
  `header=False`, row 0 belongs to the body and uses the page mode.
- `"full"` on a page full-paints the composed screen on every update. It is
  useful for authenticity or a page with complex geometry, not for a 1 Hz
  tick.

Safety barriers are automatic:

- A row containing underline or a non-normal size (`DOUBLE_HEIGHT`,
  `DOUBLE_WIDTH`, `DOUBLE_SIZE`) never uses cell runs. Underline uses the
  full-row path because it is line-affecting; non-normal size uses the normal
  `CAN`-plus-runs row path. Keep inline underline and double-size rows out of
  cell-paint designs where possible.
- Rows that the terminal has scrolled are repainted as rows; they are new
  content.

Scrolling pages still work. If the new screen is an exact vertical shift, the
normal `LF`/`VT` fast path applies. If the shifted rows keep their characters
but change attributes (a reader link highlight or selection), the renderer
emits `LF`/`VT`, repaints the revealed rows, and cell-diffs the restyled
overlapping rows. If a changed overlapping row is a barrier, the renderer
falls back to the normal non-shift diff.

Raw tick frames bypass the shadow. If a page returns raw bytes from `on_tick`,
cell paint is suppressed until the next full paint. Prefer a `Screen` tick for
a cell-painted page.

Current public callers: `903` bouncing ball, `900` clock screensaver (the
double-size minute row is a barrier), the home clock, the chyron ticker frame,
and the reader article. `StatusHeader` and `AnnouncementHeader` stay row on
purpose; the reader index stays row.

## Dynamic pages

A page can update a region without repainting the whole screen. Set
`tick_interval`, provide `on_tick`, and declare `paint="cell"` for frequent,
small changes:

```python
def screen(ctx):
    s = Screen()
    ctx.set_status("PAGE 150")
    s.text(1, 0, "DYNAMIC", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(3, 0, "VALUE: " + current_value(ctx))
    page_input(s, ctx, cursor="auto")
    footer(s)
    return s


def tick(ctx):
    return screen(ctx)


@page("150", title="DYNAMIC", tick_interval=1.0, on_tick=tick,
      paint="cell")
def dynamic(ctx):
    return screen(ctx)
```

- `tick_interval` is in seconds. `None` (the default) means static.
- `MinitelApp` calls `on_tick` while the page is current. Navigating away stops
  ticks; navigating back paints the full page once and resumes.
- **Preferred: return the complete desired `Screen`.** The session diffs it
  against its shadow. With `paint="cell"`, only the changed cell runs are sent;
  unchanged cells, inverse backgrounds, and link colours are preserved. Factor
  the body into a `screen(ctx)` helper used by `render` and `on_tick`, as the
  home clock, bouncing ball, and clock screensaver do.
- Use a fixed-width value (for example `time.strftime("%H:%M:%S")`) so the
  region never changes length and never needs clearing.
- `page_input` redraws the current field value on every render, matching
  `line_field`. A Screen tick therefore keeps typed input visible instead of
  blanking it.
- If a tick moves the cursor, use `page_input(s, ctx, cursor="auto")`. While
  the page is idle the cursor is hidden and ticks run. The first typed
  character sends `CON`, the cursor appears, and ticks pause while the line is
  non-empty. Submit, annulation, or correcting to an empty line sends `COF`
  again and resumes ticks.
- `cursor="hidden"` is also available if a page should never show a cursor.
  `cursor="visible"` with a moving tick will blink or jump: `COF`/`CON` resets
  the terminal’s blink phase, and the tick cannot sync to it.
- Local echo still lands in the inverse field while the cursor is hidden. With
  the default server echo, the server sends the same cursor commands;
  `--local-echo` keeps terminal echo instead.
- The initial `render` must draw the same region at the same position, so the
  first tick finds the same cells.
- A full page is ~240 bytes (~1.8 s at 1200). A small region is ~15 bytes
  (~0.11 s). Do not full-repaint at 1 Hz on the M1; `paint="full"` is for
  deliberate full-screen updates, not frequent ticks.

**Raw tick frames.** A page can still return only a dynamic region as raw
bytes. The session prepends a full attribute reset and appends `pos(input)`
plus the current cursor visibility, so the insertion point returns to the
`PAGE:` field with a known pen state. Raw frames bypass the shadow, so a later
cell diff cannot know what they touched: cell paint is suppressed until the
next full paint. Prefer a Screen tick with `paint="cell"` for a cell-painted
page, and keep raw frames for pages that genuinely own a tiny region and do
not need cell paint.

The timer is transport-level: `Session.next_timeout()` says how long to wait,
and `Session.on_timeout()` asks the active page for a tick, activates the
screensaver, or rotates it. `Session.tick()` remains the page-tick entry point.
Input and ticks share one writer, so a page paint is never interleaved with a
tick.

## Scrolling text pages

A page can use the Minitel's hardware scroll mode ("mode rouleau") by declaring
`scroll=True`. This is for full-screen, append-only text such as a teletype
screensaver, a vidiprinter, or a chat log.

```python
@page("902", title="SHAKESPEARE", screensaver="scroll",
      tick_interval=0.5, on_tick=scroll_tick, back_page="190",
      scroll=True)
def shakespeare(ctx):
    return screen(ctx)
```

The page directory flags scrolling pages with the `S` page flag.

- **The hardware scrolls rows 1-24. Row 0 never scrolls.** A normal page
  declares its status with `ctx.set_status(...)`; the header keeps row 0 fixed
  without the page reprinting it. A screensaver scroll page follows the other
  screensavers instead: a plain black row 0 with a short title, not the inverse
  status bar.
- **Only row 0 is fixed.** A header or footer below row 0 scrolls with the
  content. To keep one fixed, repaint it after each scroll. A two-row footer
  costs roughly 0.3-0.9 s per new line at 133 cps; four rows cost roughly
  0.6-1.5 s. Use row 0 for the most important static information and keep any
  fixed footer small.
- **Keep scrolling rows within columns 1-39.** A row that reaches column 40
  can take the terminal's overflow path on the bottom row and add an extra
  scroll, which shows as a blank line between lines. This is the terminal's
  overflow, not a second `LF` from the server: the scroll diff still sends one
  `LF` per tick. The 2026-11-04 M1 probe confirmed a 40-column row scrolls
  immediately and a 39-column row does not. The `902` page wraps its text at 39
  columns. Row 0 is outside the scroll and may use all 40 columns.
- Return a complete `Screen` from `render` and `on_tick`. When the new screen is
  the old screen shifted by one or more rows, the session emits the terminal
  `LF`/`VT` and repaints only the new rows. Otherwise the normal changed-row
  diff applies.
- A scrolling page may also declare `paint="cell"`. An exact shift still uses
  `LF`/`VT`. If the shifted rows keep their characters but change attributes
  (for example a reader link highlight), the renderer shifts, repaints the
  revealed rows, and cell-diffs the restyled overlapping rows. Barrier rows
  fall back to the normal non-shift diff.
- Do not send `LF`, `VT`, or the scroll-mode command from a page. `minitel/`
  owns the mode and the renderer chooses the bytes. Pages must not emit raw
  protocol bytes.
- Use `tick_interval` for a scrolling page. There is no page-local timer; the
  session owns the deadline, and the normal screensaver/power/carousel rules
  apply.
- Do not register input fields on a screensaver scroll page. A real user key
  wakes the screensaver as usual; the scroll's `LF`, protocol/status frames, and
  line-ending echoes do not. A normal scroll page can have a field, but the
  field line will scroll unless it is repainted or kept empty while other
  content arrives.
- Keep row 0 static during the scroll; if its content changes, the renderer
  paints it separately and the scroll fast path still applies to rows 1-24.
- The first full paint of a long text is a normal full-page paint (~7 s at
  133 cps for 24 dense lines). Later ticks are cheap: one line is about
  40 bytes plus `LF`. Choose a tick interval above the per-line cost.

The `902` Shakespeare screensaver is the reference. It bundles a public-domain
text under `pages/screensavers/_support/texts/`, wraps it to 39 columns, and
advances one line per tick using `ctx.state`. It uses the screensaver-style
black row 0 (`3615 KILO / SHAKESPEARE`) and loops after a short four-line blank
gap.

## Terminal power pause

The dongle keeps the TCP connection alive when the Minitel is switched off. The
session detects the terminal's power-off and power-on signals and pauses the
page: ticks, carousel advances, and screensaver rotation stop, and the session
writes nothing. On power-on it resets input parsing, restarts the idle clock,
and full-paints the current page or the active screensaver page. History,
fields, values, focus, and pager offsets are preserved, so a half-typed form
comes back exactly as it was.

Pages need no hook and should not implement power handling. The mechanism is
session-owned, like the screensaver. Do not assume a tick or a carousel advance
ran while the terminal was off; the session simply did not schedule one.

The byte sequences are empirical and configurable through `PowerSignals` (or
the server's `--power-off`/`--power-on` hex options). The observed power-off
byte is `00`; the observed power-on cluster is
`7c 13 59 13 53 13 54`. If your unit sends something else, configure it rather
than adding page code.

## Screensavers

A screensaver is a session-owned display takeover. It is **not navigation**: the
current page, history, field values, focus, and pager offset are preserved, and
any user key wakes back to the page the user was on. The first user-input chunk
is discarded so a stray `ENVOI` cannot navigate or type into the restored page.
Protocol/status frames, identification frames, and line-ending echoes (`LF`,
`CRLF`, `LFCR`) do not wake the screensaver and do not reset its idle timer.
This matters for scrolling pages: their `LF` is display output, not input.

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
on wake. Screensaver ticks use the page's paint mode; `900` CLOCK and `903`
BOUNCING BALL declare `paint="cell"`. The clock's double-size minute row is a
barrier and keeps the row path; only its normal-size seconds/date rows use cell
runs.

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
choose `900` CLOCK, `901` TEST CARD, `902` SHAKESPEARE, `903` BOUNCING
BALL, or `910`-`912` CAROUSEL, cycle the auto delay, and activate the current
choice with `0`.

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

A page whose carousel repeatedly replaces the main content may also set
`no_screensaver=True`. That keeps the automatic screensaver from interrupting
the content carousel; manual activation through the selector still works. A
page that only repaints a region should leave the screensaver enabled, because
the screensaver is the burn-in defence.

If a page has several ways to register its pager (normal render, `on_tick`, and
`on_submit`), declare the carousel in one helper and use that helper everywhere.
Otherwise the session sees a different declaration and restarts the interval.
This is also why the data tick must re-register the same pager with the same
policy.

The Hacker News list and sports live page are the current carousel callers.
Both declare one hold, register the same policy wherever the pager is set, set
`no_screensaver=True` because the main content changes, and leave their data
ticks in place. All of the timing remains in the session; the pages gain no
timer code.

## Partial updates

The session keeps a shadow `Screen`. `Session.refresh()` re-renders the current
page and returns `Action(raw=render_diff(old, new))`. `ANNULATION` uses it, and
a `Screen` returned by `on_tick` is diffed.

The update mode is per page and per header:

- `None`/`"row"` repaints whole changed rows. This is the default and is right
  for normal page changes.
- `"cell"` writes adjacent changed cell runs and preserves unchanged cells,
  including inverse backgrounds and colours. Use it for small, frequent
  updates; a footer row is still ~40 bytes, but a one-digit clock change is a
  handful.
- `"full"` full-paints every update. It is for authenticity or a whole-screen
  replacement, not a 1 Hz tick.
- Underline and non-normal-size rows never use cell runs. Scrolled/revealed
  rows are repainted as rows.

A page declares the body mode with `@page(paint=...)`; a header declares row 0
with `Header.paint`. A returned `Screen.paint` overrides either for one frame.
See [Update paint modes](#update-paint-modes).

Raw tick frames bypass the shadow. If a page returns raw bytes from `on_tick`,
cell paint is suppressed until the next full paint. A later `refresh()` may
repaint rows that changed through raw frames; that is correct but less
efficient. Prefer a Screen tick for a cell-painted page.

Form focus uses `refresh()` and the diff, so a footer built from
`ctx.active_name` updates automatically. Only the footer rows and cursor are
sent.

## Live data and services

Keep network calls out of `render`, `on_submit`, `on_key`, and `on_tick`. Fetch
in a background thread, cache the result, and render from the cache.

Background services live in `services/` and are discovered at startup:

```python
page_registry = pages.build_registry()
service_registry = services.build_registry()
missing = page_registry.missing_requirements(service_registry)
if missing:
    raise SystemExit(f"missing services: {missing}")

app = MinitelApp(
    page_registry,
    initial="100",
    fallback=page_registry.get("__not_found__"),
    services=service_registry,
)
```

A service package exports one decorated builder:

```python
from minitel.data.services import service

@service("weather", description="Open-Meteo current conditions")
def build_weather_service():
    return WeatherService()
```

The decorator returns a `ServiceSpec(key, factory, description)`; the factory
must be cheap and side-effect free. `ServiceRegistry.discover("services")`
imports the package tree, sorts specs by key, builds each once, and rejects
duplicate keys. `ServiceRegistry.start()` runs in key order; `stop()` runs in
reverse order in a `finally` block. Hooks are optional and may be normal
functions or coroutines.

Pages declare their dependencies:

```python
@page("150", title="LIVE SCORES", requires=("sports",))
```

The server validates the full page/service graph before listening. Pages read
declared services with `ctx.service("sports")`; an undeclared key raises
`KeyError` instead of silently reaching into the process-wide service mapping.
Pages never construct a service or import its provider module. `minitel/` stays
content-free; `services/` owns background data and lifecycle; `pages/` owns
presentation.

The library pieces:

- `minitel/data/cache.py` - `ResourceCache.get(key, loader)` returns a `Snapshot`
  immediately and starts at most one daemon loader per key. A `Snapshot` has
  `value`, `loaded_at`, `error`, `loading`, `has_value`, and `age()`. On a failed
  refresh the old value is kept and `error` is set. `load_now()` is synchronous
  and exists for tests and prewarming; `retry()` clears a failed-load backoff
  and triggers a fresh load. Inject `clock` and `thread_factory` for
  deterministic tests.
- `minitel/data/http.py` - `get_json(url, headers=None, timeout=10.0)` raises
  `HttpError` with `status`, `body`, and `retry_after`.
  `get_json_response(...)` returns a `JsonResponse(payload, status, headers)`
  when a service needs response headers such as rate-limit counters.
- `minitel/text.py` - `plain`, `sanitize`, `fit`, `wrap`, `domain`, and `age`.
  Remote text is not guaranteed to be encodable: HTML tags, entities, curly
  quotes, emoji, and non-Latin scripts will crash the renderer if passed
  straight to `Screen.text`. Run every fetched title, author, domain, and
  comment through `sanitize` first.
- `minitel/design/pager.py` - a frozen `Pager(total, page_size, offset)` with
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
- `services/news/service.py` owns the Hacker News URLs and field names, parses
  `Story`/`Comment` objects, and wraps one `ResourceCache` for the front page
  and one for comments. The cache does not block a page paint; the first paint
  shows `LOADING` and a later tick shows the data.

The weather page is a second, deliberately different cached source:

- `services/weather/service.py` owns the Open-Meteo URL, the location table, WMO
  condition labels, and one cache entry per city. Each city is a separate key,
  so one failed location does not hide the others.
- `pages/weather/page.py` renders one row per city with current temperature,
  condition, and today's low/high. It derives `LOADING`, `UNAVAILABLE`, and
  `OFFLINE - CACHED` from the snapshots and ticks every 30 seconds to pick up
  background loads.
- The page credits Open-Meteo. The source is keyless and uses only the standard
  library.

The sports service is the reference for a keyed, shared, live feed:

- `services/sports/source.py` owns football-data.org v4 URLs, the `X-Auth-Token`
  header, status and team normalisation, and parsing. `get_json_response` is
  used so the source can read `x-requests-available-minute` (the documented
  `X-RequestsAvailable` alias is also accepted) and `X-RequestCounter-Reset`.
- `services/sports/feed.py` is the only poller. Pages call
  `ctx.service("sports").snapshot()` and never fetch. The snapshot is an
  immutable `FeedSnapshot` with `matches`, `alerts`, `loaded_at`, `updated_at`,
  `error`, `loading`, and quota fields. A failed refresh keeps the last good
  snapshot.
- `pages/sports/live.py` is `150` and the `5` alias. One page is one league:
  the title is `LIVE SCORES - PL`, kickoff times are section headers, and the
  matches under each time are laid out in two `HOME SCORE AWAY` columns. A
  league with more than ten time-pair rows continues on another page; the
  session pager moves through league pages with a 30-second `Carousel` on idle.
  Numeric `1`-`N` opens detail, and the complete `Screen` is returned from
  `on_tick` so the session diffs it.
  `151` declares `back_page="150"`; `153` is the read-mostly table sibling;
  `154` shows the provider, quota, poll intervals, and last error. Today's
  finished matches already appear on `150`, so there is no separate results
  page.
- Poll intervals adapt to the snapshot: live, near kickoff, or idle. Do not add
  a page-local timer. A free football-data.org token returns delayed scores and
  no goal events. `FeedSnapshot.goals_available` records whether the provider
  included events; the detail page shows the goal list only when there are
  goals, and otherwise omits the block (or shows one compact plan note). The
  pages show `UPDATED` and never claim real-time.

Configuration and secrets:

- Copy `.env.example` to `.env`; `.env` is tracked by neither the inner nor the
  outer Git repository. `services/common/config.py` loads simple `KEY=VALUE` lines
  from the current directory or the repository root and calls
  `os.environ.setdefault`, so an exported variable wins.
- The key is `FOOTBALL_API_KEY` (or `FOOTBALL_DATA_TOKEN`). Other settings are
  `FOOTBALL_API_BASE`, `FOOTBALL_COMPETITIONS`, the three intervals, the retry
  delay, and the timeout.
- Never log, render, or include a token in an error message. `HttpError` carries
  the URL, status, body, and `Retry-After`, not request headers.

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

The home menu is built from the registry, not from a list in `pages/home.py`.
A page joins the menu when it declares a **1-2 digit numeric alias**
(`"1"`...`"99"`):

```python
@page("150", title="LIVE SCORES", aliases=("5",))
```

Rules:

- one line per page; if a page has several numeric aliases, the lowest is shown;
- entries sort numerically, so `1, 2, 3, ... 10, 11` stay in human order;
- the home page itself (`""`, `"0"`) is excluded;
- non-numeric aliases remain direct-entry keys only;
- the lowest 10 entries are shown; the hint reports `(+N MORE)` and every page
  remains reachable by number and on page 199;
- the title comes from `Page.title`, so a page with a numeric alias
  publishes its title on the home menu. Use a neutral title or no alias when
  that matters.

To put a page on the menu, add an alias. To keep it off the menu while still
supporting direct entry, use a non-numeric alias or no alias.

Keep page numbers stable and descriptive. The example scheme is:

| Number | Page |
|---|---|
| `100` | home / index |
| `110` | news service directory |
| `111` | Hacker News headline list |
| `112` | story detail |
| `120` | weather: current conditions, forecast, and `120#CODE` city detail |
| `130` | about / guide |
| `140` | guestbook |
| `150` | live scores or next fixtures (`5`), `150#CODE` league direct entry; `151` match detail |
| `151` | match detail |
| `153` | league tables, `153#CODE` direct entry |
| `154` | feed status |
| `190` | screensaver selector (`7` on the home menu) |
| `199` | hidden developer page directory; not linked from home |
| `900` | CLOCK screensaver |
| `901` | TEST CARD screensaver |
| `902` | SHAKESPEARE scrolling text screensaver |
| `903` | BOUNCING BALL screensaver |
| `910`-`912` | CAROUSEL promo frames |
| `__not_found__` | fallback |

Page numbers and aliases are keys. Duplicates within one package are startup
errors; across packages, a later package overrides an earlier claim with a
startup report. The example service uses `100`-`199` and `900`-`912`. An
additional package can reserve its own page-number range; see
[Loading another page or service package](#loading-another-page-or-service-package).

## Page extension codes

A page can expose sub-addresses by declaring `extensions=True`:

```python
@page("160", title="DEX", extensions=True)
def dex(ctx):
    token = ctx.extension          # None on 160, "1" on 160#1
    ...
```

The registry parses the route; pages never split `#` themselves.

- Syntax is `base#token`, for example `120#PAR`, `153#PL`, or `160#151`.
  The league tables page is the current reference: `153#PL` selects the
  configured `PL` competition.
- The base must be a registered page number or alias and must declare
  `extensions=True`. Otherwise the key is not found.
- A token is 1-6 uppercase ASCII alphanumerics after normalisation. Input is
  case-insensitive: `120#par` becomes `120#PAR`.
- `#` is the canonical separator. `£` is accepted as an input alias because the
  Videotex glyph for byte `0x23` may be `£`; both become `#` internally.
- Empty tokens, multiple separators, spaces, and non-alphanumeric characters
  are invalid routes.
- The page validates the token's meaning. An unknown token is a page-level
  message (`NO CITY: XYZ`), not the generic not-found page.
- `ctx.extension` is `None` on the base page and the canonical token on an
  extension route. It is available in `render`, `on_submit`, `on_form`,
  `on_key`, and `on_tick`.
- `ctx.take_extension()` returns the token once after navigation to the route,
  then `None`. Use it when the token selects a session cursor or one-shot
  state; use `ctx.extension` every render for a stable view. History restore
  does not reapply the token, so returning from a detail page keeps the
  remembered cursor. `150#PL` uses this; `120#PAR` does not need it.
- `ctx.page.number` is the full key (`120#PAR`). History, pager memory, and
  page-message keys use the full key, so extension routes have their own
  remembered cursor and messages.
- `RETOUR` follows history by default. Direct entry from home returns home; if
  you reached `120#PAR` from `120`, it returns to `120`. A page can declare
  `extension_back_page="120"` to make the summary a logical parent: direct
  `120#PAR` then returns to `120`, and the next `RETOUR` follows history. The
  base page is not automatically the extension route's parent.
  Page 120 uses this for `120#PAR` city detail.
- An alias resolves to the canonical base: `5#PL` addresses `150#PL`.
- Extension routes are not registered pages. `Registry.all()`, the page
  directory, screensaver groups, and startup requirement validation list base
  pages only. The page directory marks extension-aware base pages with the `#`
  page-number marker.
- Do not declare `extensions=True` on screensaver pages in the current version;
  extension routes are not part of screensaver groups. Markers and flags are
  independent; the directory renders every applicable one.
- Keep the existing one-cursor rule. An extension that selects a pager or form
  cursor uses `take_extension()` so `SUITE`/`RETOUR` are not fought on every
  render; stable single-view routes read `ctx.extension`.

To test a route without a socket:

```python
session.navigate("120#PAR")
assert session.current.number == "120#PAR"
```

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
python3 run_server.py --port 43620 --cps 0
python3 tools/minitel_client.py --connect 127.0.0.1:43620
```

The interactive client renders the live session and sends real Minitel keys.
The server defaults to server echo, so start the client with `--no-local-echo`
to match; if the server runs with `--local-echo`, the client default matches.
`F9` shows the key map, and `Ctrl+Q` quits.

For a one-shot capture or a replayable plain grid:

```sh
python3 tools/virtual_minitel.py --connect 127.0.0.1:43620 --plain
```

`--cps 0` disables pacing for a fast local test. The real M1 uses `--cps`
default (1200/9).

## Using AI to write pages

Give the model a small, concrete context:

- this document,
- `pages/home.py` and `pages/common/`,
- `minitel/pagemodel/` and `minitel/render/`,
- the test command.

A prompt that works well:

```
Add a Minitel page in pages/ using the existing library.
- Use @page from minitel and Screen.
- Use pages.common.layout.status/footer and pages.common.widgets.page_input.
- Keep to 40 columns and rows 0-24; row 0 is status, row 20 is PAGE, row 22 is footer.
- Call page_input(s, ctx) for a single field, or ctx.add_field(...) and
  form=True/on_form(ctx, values) for a multi-field form.
- Use ctx.state for per-session data.
- Add a 1-2 digit numeric alias to put the page on the home menu.
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

## Loading another page or service package

The default entrypoint discovers `pages` and `services`. An additional package
can add pages, services, or both without changing the public tree. This is how
an additional package stays separate from the published code.

```sh
uv run python run_server.py \
  --extra-path ../extra_pages \
  --pages-package extra_pages \
  --services-package extra_services
```

- `--extra-path PATH` prepends a directory to `sys.path`; repeat it for more.
  `PYTHONPATH` works too.
- `--pages-package NAME` and `--services-package NAME` are repeatable.
- The packages are ordinary module packages discovered by `Registry.discover`
  and `ServiceRegistry.discover`; subpackages are walked.
- `requires=("extra_service",)` is validated against the composed service
  registry.
- The home menu and page 199 use the composed registry and its resolved
  aliases, so an overridden alias appears once, on the winning page.
- The package is content, not a fork: import `minitel` and `pages.common` as
  usual. Public code must not import the additional package.

### Page and alias overrides

Pages from extra packages compose in load order: the public `pages` package
first, then each `--pages-package` in the order given. A later package may
reuse a page number or alias:

- **Page-number override**: the later page replaces the earlier page at that
  number. The earlier page is removed from the composed registry. Its aliases
  disappear unless the new page declares them; the startup report lists moved
  and removed aliases. References to the number (`back_page`, links, extension
  bases) now reach the replacement.
- **Alias override**: the later page takes the alias and home-menu slot. The
  earlier page remains reachable at its canonical number. This is the usual way
  to keep the earlier page available for testing while giving a replacement
  page the menu slot.
- **Same package**: duplicate page numbers or aliases are still errors. Only
  cross-package overrides are allowed.
- **Startup report**: `run_server.py` prints a warning listing each override
  and its package chain. `--strict-overrides` turns the report into a startup
  failure.
- **Services are not layered**: duplicate service keys remain startup errors.
  An additional service uses a new key.

Example: a later page can take an existing menu alias while the earlier page
stays reachable by its number.

`pages.build_registry("extra_pages")` and
`services.build_registry("extra_services")` provide the same composition for
a custom launcher.

Direct entry, the home menu, and page 199 do not authenticate the user; the
server still listens on its configured host and port. Access control is
separate: any connected user can visit any page on the server.

## Extending beyond pages

The library boundaries are deliberate:

- **New terminal profile**: add a `TerminalProfile` and a `by_type` mapping in
  `minitel/terminal/profiles.py`.
- **New transport**: implement `serve`/`paced_write` in
  `minitel/transport.py`; `Session` does not know about sockets.
- **Different application**: build a `Registry`, pass a fallback and guide page
  to `MinitelApp`, and choose a page package (not necessarily `pages/`).
- **Background services**: injection, `ctx.service`, and `start()`/`stop()`
  hooks are implemented. The news source is the reference for a cached live
  feed. A shared scheduler, a multi-user hub, and push updates are still future
  work above `Session`.
- **Forms**: multi-field focus and `on_form` are implemented. Field masks,
  validators, and cursor/insert editing are natural extensions of `Session`.
- **Themes**: copy `pages/common/` or create another layout package. The core
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
- Scrolling text pages declare `scroll=True`; row 0 is the only fixed chrome.
  Return a full `Screen` and let the session emit the scroll bytes.
- Content carousels are declared on the pager, not implemented with page-local
  timers. Pages that repeatedly repaint the main content on idle through a
  carousel may set `no_screensaver=True`; region-only updates should leave the
  screensaver on.
- Keep `minitel/` free of application content; keep `pages/` free of protocol
  byte wrangling.
