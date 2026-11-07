# Changelog

## Unreleased

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
- Added native Minitel scroll mode (`@page(..., scroll=True)`) and the `902
  SHAKESPEARE` scrolling-text screensaver, including scroll-aware rendering,
  screensaver wake filtering, virtual terminal support, and the 39-column
  scrolling layout.
- Added page extension codes (`page#token`) for direct links to sub-views:
  `153#PL` league tables, `120#PAR` weather city detail, and `150#PL` live
  scores league selection. The page directory marks extension-aware pages with
  the `#` page-number marker and scrolling pages with the `S` page flag.
- Sports live scores fall back to the next matchday with fixtures when today
  has no matches; the page shows `NEXT FIXTURES` with the date.

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
