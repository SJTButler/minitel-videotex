# Changelog

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
