# Changelog

## Unreleased

- Added update paint modes: pages and headers can declare `paint="cell"` for
  changed-cell runs, `paint="row"` for the default changed-row diff, or
  `paint="full"` for every-update full paints, with a per-frame `Screen.paint`
  override. Cell paint preserves unchanged inverse/colour cells and only uses
  row clears for underline, non-normal-size, or scrolled rows. The bouncing
  ball, clock screensaver, home clock, chyron ticker, and reader article opt in;
  `page_input` now redraws the current field value for Screen ticks, and the
  reader handles scrolling that also restyles link highlights. The status and
  static announcement headers deliberately keep row paint; the chyron ticker
  uses cell paint.
- Added a row-0 header surface: pages declare their status with
  `ctx.set_status`, a page can opt out or select a page-specific header, and
  the session composes the header over the body. Announcements are session-owned
  (sources, channels, queue, watermark) and rendered by the header; live sports
  goals appear on any page, the reader keeps its `FIND:` row when idle, channel
  overrides compose across packages, and `--no-announcements` /
  `--no-announcements-on-screensaver` control the feature. The server log
  records the caller for newly seen announcements. Diagnostics page `985`
  provides a deterministic announcement source for testing. An optional
  right-to-left chyron header is selectable with `--chyron`.
- `Carousel` policies can carry a page subset: timed advances skip pages such
  as past results or future fixtures while manual paging still visits all
  pages.
- Added extra package composition: `pages.build_registry(*packages)` and
  `services.build_registry(*packages)` discover additional page and service
  packages, and `run_server.py` accepts repeatable `--pages-package`,
  `--services-package`, and `--extra-path` options.
- Extra page packages now layer in load order: a later package can override a
  duplicate page number or alias, with a startup override report and
  `--strict-overrides` to fail instead. Same-package duplicates and service
  keys remain startup errors.
- The home menu is derived from 1-2 digit numeric page aliases instead of a
  hardcoded list; the lowest 10 are shown, with a `(+N MORE)` hint when
  truncated.
- Startup now reports services that no composed page requires, without
  changing service lifecycle or pruning anything.
- Added a session-owned `Viewport` cursor for long-text pages and a full-screen
  football vidiprinter (`155`, alias `6`) with a 200-alert history and
  current-day backfill from goal events.
- The vidiprinters force one full bottom-up repaint when their first data
  arrives after loading.
- The public vidiprinter shows the competition and highlights the event team;
  live alerts stay in arrival order because the free feed can lag.
- Match detail is addressable by team code (`151#ARS`, or `151#ARSHUL` for an
  exact pair); selecting a match from live scores uses the pair route.
- Added native Minitel scroll mode (`@page(..., scroll=True)`) and the `902
  SHAKESPEARE` scrolling-text screensaver, including scroll-aware rendering,
  screensaver wake filtering, virtual terminal support, and the 39-column
  scrolling layout.
- Added the `160 WIKIPEDIA` linked reader: live MediaWiki search/parse, a
  stdlib HTML-to-reader parser, batched link resolution, base36 page tokens,
  cached documents, hidden live input fields, colour-only link anchors with
  inverse selection (headings use inverse) and prefix rollback, and viewport
  match stops cycled by `SUITE`/`RETOUR`. The search index uses a session-owned
  `Choice` pager-of-pagers: `SUITE`/`RETOUR` select articles and advance the
  outer page at the boundary, while `ENVOI` opens the selected result. Returning
  from an article restores the last query and selection; an empty query is a
  prompt rather than a loader. The page tests use a fixture source. Inline
  underline is not used on the M1 (it is
  row-scoped); whole-line underline runs are closed explicitly and their rows
  repaint fully. The home alias and two-column menu remain separate work.
- Added page extension codes (`page#token`) for direct links to sub-views:
  `153#PL` league tables, `120#PAR` weather city detail, and `150#PL` live
  scores league selection. The page directory marks extension-aware pages with
  the `#` page-number marker and scrolling pages with the `S` page flag.
- Sports live scores fall back to the next matchday with fixtures when today
  has no matches; the page shows `NEXT FIXTURES` with the date.
- Added an optional `diagnostics_pages` package (`980`-`984`) for reproducing
  input latency, full-paint starvation, idle-connection loss, reset signals,
  and page-handler faults on the Minitel. The app now logs a session traceback
  when a page handler raises instead of closing silently.

## 0.3.0 - 2026-11-02

- Split `minitel/` into ownership packages: `protocol/`, `terminal/`,
  `render/`, `design/`, `pagemodel/`, `session/`, and `data/`.
- Moved `Pager`, `Carousel`, and `InputField` into `minitel.design`.
- Decomposed `Session` into navigation, editing, idle, power, and action
  modules while keeping the public `Session` API.
- Added connection-level output pacing.
- Narrowed `PageContext`: declared services only, no live session or raw
  service mapping.
- Established `pages/common/` for shared presentation and `_support/` for
  feature-private helpers.
- Moved page copy and display labels out of services.
- Fixed registry idempotence, screen size validation, form/pager exclusivity,
  tables error clearing, and service shutdown resilience.
- Added boundary and package-layout tests.
- Declared the M1-only capability baseline.
- Added MIT licensing and packaging metadata.
