# Page recipes

This catalogue shows the supported page shapes and the trade-offs behind them.
It is **not** a second API contract. The normative reference is
[`authoring-pages.md`](authoring-pages.md); when this page and the authoring
guide disagree, the authoring guide wins. Mechanism tests enforce behaviour.

Use the recipes to choose a shape, sketch a layout, and avoid patterns that
fight the session. Do not copy a whole page from here: copy the shape and read
the real page for the current API.

## Choosing a shape

Ask two questions first: does the content move the whole screen, or only a
region, and does the user need two interactions at once?

| Need | Shape |
|---|---|
| One interaction, a list of records | index page + detail page; `Pager` or `Choice` |
| One interaction, a long document | scroll page with `Viewport` (and `Stops` for find) |
| A query and its results | pane page: form region + results region |
| Two peer lists that the user browses | pane page: two Choice regions |
| A filter or mode plus a live list | pane page: Choice + Choice or Choice + Pager |
| Two independent forms | separate pages, or a later form-scoping mechanism; not one form region |
| A confirmation | a focusable region, or a separate transient page |

Defaults worth keeping:

- **Index + detail as two pages** is cheaper and simpler than two panes. The
  terminal is 40 columns; two always-visible datasets leave little room for
  labels. Use two panes only when the user genuinely compares or hops between
  them.
- **A page-at-a-time list** beats a viewport for records. `SUITE`/`RETOUR`
  repaint one window and the selection is visible; a viewport is for prose,
  logs, and long lines.
- **Commit on `ENVOI`** when one pane chooses what the other pane shows. Live
  preview repaints the second pane on every cursor move at 1200 baud and makes
  `RETOUR` semantics ambiguous.
- **Rows 1-24 belong to the page.** Row 0 is the header (D039). A footer inside
  the body is page drawing and costs its row bytes on every scroll update.

## Pane recipes

Pane pages are pages without `scroll=True`. They use named regions when more
than one interaction is visible. The page draws every rectangle; the session
owns the cursors, focus, declared edges, and history.

### Form + results (`170 TRAIN TIMES`)

The first real regions caller: a form region on top, a pager region below.

```text
row 0   TRAIN TIMES                         PAGE 170
row 1   TRAIN TIMES
row 2   FROM: [PAD]   TO: [___]
row 3   DEPARTURES FROM PADDINGTON
row 4   TIME  DESTINATION           PLT STATUS
row 5   10:42 READING               4   ON TIME
row 6   10:48 OXFORD                1   ON TIME
...
row 17  1/3
row 19  SOURCE: REALTIME TRAINS
row 22  SUITE=NEXT  RETOUR=BACK  SOMMAIRE=HOME
```

```text
regions:  form --SUITE--> results
          form <--RETOUR-- results
keys:     ENVOI in form: submit query, focus results
          SUITE/RETOUR in form: move fields
          SUITE/RETOUR in results: move pages
          RETOUR at results page 1: focus form
          RETOUR at the first field: history/back_page
```

Use `Region.key=query` on the results region so a new query starts at page 1
and a repeated query returns to its own page. The page reads the submitted
values; the session keeps the cursor.

### Choice + choice (`171 RAIL EXPLORER`)

Two selectable panes with a page-owned path and a back stack. The right pane is
a live Choice of onward departures; the left pane is the current train's
calling points.

```text
row 0   RAIL EXPLORER                       PAGE 171
row 1   RAIL EXPLORER
row 2   17:22 FROM FRATTON
row 3   LOADING TRAINS...
row 4   CALLS                 | FROM HAVANT 17:28+
row 5   TIME  STATION         | TIME  DESTINATION  PLT
row 6   17:22 FRATTON         | 17:35 ANGMERING     2
row 7   17:28 HAVANT          | 17:40 BRIGHTON      1
...
row 18  1/1                   | 1/1
row 20  PATH FRATTON > HAVANT 0:13
row 21  SOURCE: REALTIME TRAINS
row 22  ENVOI=TAKE TRAIN
row 23  RETOUR=BACK  SOMMAIRE=HOME
```

```text
regions:  calls --ENVOI--> trains
          calls --RETOUR--> page_back
          trains --RETOUR--> page_back
keys:     SUITE/RETOUR move the focused selection
          ENVOI commits the selection and the page changes state
          RETOUR at a selection boundary pops the page's snapshot
```

The page owns a LIFO stack of snapshots: content, focus, and the region keys
that scope remembered cursor state. `on_back` pops one and returns true. The
session does not know the path; it only calls the hook at the declared
boundary. An empty stack follows `back_page`/history. When the popped snapshot
restores an earlier region key, the session restores that key's remembered
selection and page, so both panes return to their previous highlights. See
`pages/rail_explorer.py` and `tests/test_rail_explorer.py`.

Do not add a third breadcrumb cursor for the path. The page already knows the
path; it is content, not navigation.

### Form + choice + pager

The three-cursor shape for a page with a query, a selectable result, and a
detail pager. This is a supported composition, covered by
`tests/test_region_conformance.py`; no production page needs it yet.

```text
regions:  form --SUITE--> choices --SUITE--> results
          form <--RETOUR-- choices <--RETOUR-- results
keys:     ENVOI in form: validate and focus choices
          ENVOI on a choice: commit it and focus results
          SUITE/RETOUR in results: page the detail
          RETOUR at the first form field: history
```

Keep one form region. The session has one field/value/focus set per page in
this slice; two independent forms need page-scoped field state, which is a
separate mechanism. A `form=True` page may still have Choice and Pager regions
as long as the choices and pagers are declared with `region=`.

### Conditional panes

A region may disappear when its data is empty or a mode is off. The page calls
`ctx.set_regions(...)` with only the regions that exist for that render, and
adjusts the edges so no edge points at an absent region.

```text
full:     folders --SUITE--> messages --SUITE--> reply
empty:    folders --SUITE--> reply
```

Focus fallback is session-owned: current region, then remembered focus for the
page, then `default_focus`. A Choice that is removed and later re-declared with
the same `Region.key` restores its page and selected index. Do not point at the
absent region from a surviving edge; validation rejects unknown edges.

Use a conditional region for empty folders, filtered lists, and advanced
panes. Do not render a fake empty cursor just to keep the graph stable.

### Modal-like confirmation

There is no overlay mechanism. Two supported choices:

- **A focusable region** in the same page: `confirm` region with `prev=` the
  pane that opened it, and a page-owned state flag. The user sees the question
  beside the content and `RETOUR` leaves the confirmation.
- **A separate page**: the confirmation is a normal page with a short form or
  two-choice region. This is simpler and keeps the first page stateless.

A general overlay/dialog is deferred. Do not draw a box over a pane and call it
modal: input routing, repaint diffing, and `RETOUR` would be page-local.

### Multi-step path and back stack

When each `ENVOI` changes the page's content shape, the page owns a snapshot
stack. The recipe is:

1. Choose content keys before the transition (`train id`, `folder`, query).
2. Push a snapshot of everything that defines the screen: content state,
   focus, and the keys that scope region memory.
3. Change content and call `ctx.focus_region(...)`.
4. In `on_back`, pop one snapshot, restore it, return true.
5. Bound the stack; the rail explorer keeps 20 entries.
6. On a fresh route (a new extension token), clear the stack.

Do not put cursor objects in the snapshot. The session restores `Choice`
selection/page and pager offset from the keyed memory; the page restores the
content key and focus.

### Directory and menu pages

A directory is a list of links, not a new cursor mechanism. Use a `Choice` when
the user selects one row and `ENVOI` opens it, or draw a numeric key table when
the page is a stable index (`110 NEWS`, `190 SCREENSAVER`). Keep home-menu
aliases numeric and page-number based; the menu is derived from aliases, not a
hardcoded list.

## Scroll recipes

Scroll pages declare `scroll=True`. They use hardware `LF`/`VT`; the renderer
moves the terminal, not a pane window. Pane and scroll modes are mutually
exclusive (D047): no `Pager`, `Choice`, `Carousel`, or form region on a scroll
page, and no viewport region on a pane page.

### Article reader with a pane index (`160` -> `161`)

The reader split is the reference: `160 WIKIPEDIA INDEX` is a pane page with a
Choice over results and a live search field; `161 WIKIPEDIA PAGE#TOKEN` is a
scroll article with one `Viewport` and `Stops` for find matches. The index is
paged because it is a list; the article is scrolled because it is prose. Do not
try to put the article in a pane beside the index.

### Live log / vidiprinter (`155`)

A scroll page is the natural fit for a growing log: one `Viewport` with
`follow=True` keeps the tail visible, and `SUITE`/`RETOUR` step one line while
the data tick appends lines. The footer and source line sit in the page body;
each repainted row costs bytes, so keep the footer short and stable. If the
page changes on idle, omit the screensaver rather than adding a page timer.

### Screensaver auto-scroll (`902`)

A screensaver may use hardware scroll for a long text. The `Screensaver` owns
the page sequence and idle delay; the page owns the lines and the viewport. Do
not build a page-of-pages for "all" or put screensaver page numbers in
`minitel/`.

### Long-document find and stops (`161`)

`ctx.set_stops(...)` is viewport metadata, not a second cursor. The session
cycles matches, starts at the topmost visible one, wraps, and reveals the
selection. The page draws highlights from `ctx.stops`. Keep find state in the
page/service, not in a second scroll offset.

Hardware limits that make scroll different from panes:

- Rows 1-24 move as a block; a fixed in-body header/footer must be repainted.
- Row 0 is the only hardware-fixed row.
- Keep scrolling text within columns 1-39; a full-width bottom row can add an
  extra scroll.
- A full page is roughly 240 bytes at 1200 baud; a small pane region is much
  cheaper. Choose scroll for prose, not for a four-row list.

## Direct entry

Direct entry is a page key the user can type. It is separate from the home
menu. Two mechanisms:

- **Alias**: another registry key for the same page, usually 1-2 digits
  (`7` -> `170`). Aliases are menu entries when numeric and short; empty or
  non-numeric aliases are direct-entry keys only.
- **Extension**: `base#token` (`120#PAR`, `150#PL`, `161#TOKEN`). The base page
  must declare `extensions=True`. Tokens are uppercase alphanumeric and capped
  at six characters. The page validates its own token with `ctx.take_extension()`
  when it should apply once on entry, or reads `ctx.extension` for a stable
  view.

Useful direct entry:

- A self-contained detail route: `112` story detail with `back_page="111"`, so
  typing `112` directly still returns to the list first.
- A stable window: `150#PL` opens the Premier League page once; ticks and
  `SUITE` keep the chosen window.
- A compact composite token: `170#WATHXX` is origin + destination because the
  3-character CRS codes and the six-character cap make a joined token useful.
  `170#WAT` is origin only.
- A page that explains its own routes when entered bare: `171` shows
  `USE 171#FROM OR 171#FROMTO` rather than guessing a state.

Non-useful direct entry: a long, unstable token for transient selection, a
route that assumes a previous page's form values, or a detail page with no list
fallback. A direct route should be self-contained or explain what is missing.
Do not make a direct-entry page depend on session history that will not exist.

Aliases versus extensions: use an alias when the page is the same screen under
another name; use an extension when the token selects a window or record. Do
not register literal extension keys (`page("171#FTN")`); the registry parses
the route and the page validates the token.

## Anti-patterns

- **Page-local `SUITE`/`RETOUR`.** The session owns cursor movement and
  boundaries. A page that handles them in `on_key` will disagree with focus,
  history, and the screensaver.
- **A viewport region inside a pane page.** The two modes are exclusive
  (D047). Use a scroll page, or split the content.
- **Two live scroll regions.** A pane cannot offer a second hardware scroll
  area; hardware scroll moves all body rows.
- **Fixed in-body chrome under a scroll.** It must be repainted on every
  append and costs bytes. Use row 0 or accept the cost deliberately.
- **Arbitrary `on_retour` callables.** Use `Region(prev="page_back")` and an
  `on_back` hook that restores page state. Do not let a page implement
  navigation policy.
- **Long or unstable extension ids.** The cap is six characters and the route
  is visible to the user. Prefer short codes with a clear fallback.
- **Direct entry to a stateful page without a fallback.** If the token is
  missing, show a chooser or usage line instead of crashing or guessing.
- **One form region for two independent forms.** The current slice has one
  field/value/focus set per page. Use two pages or wait for scoped form state.
- **A third cursor for a breadcrumb.** The path is content; a back stack plus
  the page's state is navigation. Do not add a cursor the user must steer.
- **Assuming a selection follows an item.** `Choice.selected` is an index. A
  live list that reorders items must change the `Region.key` or accept index
  semantics.

## Worked layouts

### Index + detail (`110` -> `111` -> `112`)

```text
110 NEWS                 111 HACKER NEWS            112 STORY
row 1  NEWS              row 1  HEADLINES           row 1  STORY TITLE
row 2  1 HACKER NEWS     row 2  1 STORY A           row 2  BY AUTHOR
row 3  2 WEATHER         row 3    BY AUTHOR          row 3  SOURCE
row 4  ...               row 4  2 STORY B           row 4  TEXT
                         row 17 1/8                row 17 1/12
row 22 ENVOI=OPEN        row 22 ENVOI=OPEN          row 22 RETOUR=BACK
```

Ownership: the list page owns the curated index; each list page owns its
pager/Choice; the detail page owns the record and `back_page` points at its
list. A direct `112` returns to `111` first, then history.

### Form + results (`170`)

```text
regions:  form[next=results]  results[prev=form, key=query]
content:  origin, destination, departure board
state:    page owns the query and formatting; session owns field focus,
          pager offset, and the submitted values
repaint:  form focus is a cursor move; a new query repaints the results window
```

### Choice + choice with a path (`171`)

```text
regions:  calls[next=trains, prev=page_back, key=train id]
          trains[prev=page_back, key=alight station]
content:  phase, origin, filter, train, alight, path, elapsed time, stack
state:    page owns content and the LIFO stack; session owns selection,
          page, focus, and the boundary dispatch
repaint:  SUITE changes one highlight; ENVOI changes the pane shape and
          focuses the next region
```

### Conditional mail triage (generic three-pane example)

```text
full:       folders --SUITE--> messages --SUITE--> reply
empty:      folders --SUITE--> reply
focus:      folders (default); messages only when the folder has mail
keys:       ENVOI commits the folder, then the message; RETOUR pops one
            level, then leaves the page when the stack is empty
state:      page owns folder/message ids and drafts; session owns the cursors
```

This shape needs a page-owned back stack because each `ENVOI` changes content.
It is not a reason to add a generic page-stack library: a second real page must
need the same thing before that mechanism is promoted.

## References

Real callers:

- `170` train times: `pages/train.py`
- `171` rail explorer: `pages/rail_explorer.py`
- news list/detail: `pages/news/`
- Wikipedia index/article: `pages/wikipedia/`, `pages/common/reader.py`
- sports live/detail/tables/vidiprinter: `pages/sports/`
- screensavers: `pages/screensavers/`
- home menu and directory: `pages/home.py`, `pages/page_directory.py`

Mechanism tests:

- `tests/test_regions.py` - pager/form regions and validation
- `tests/test_region_state.py` - Choice memory, live totals, and conditional
  restore
- `tests/test_region_conformance.py` - three-region routing, conditional
  focus, the three-choice graph, and tick re-declaration
- `tests/test_rail_explorer.py` - the Choice+Choice caller and back stack
- `tests/test_reader_page.py`, `tests/test_reader_render.py` - scroll reader,
  viewport, and stops
- `tests/test_choice.py` - Choice value semantics

Read the code and tests for the current contract; this catalogue deliberately
does not duplicate page code.
