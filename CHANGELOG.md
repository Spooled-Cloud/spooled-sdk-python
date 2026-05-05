# Changelog

All notable changes to the Spooled Python SDK are documented here.

## [1.0.13] - 2026-05-05

### Fixed

- **AsyncWorker**: replaced deprecated `asyncio.get_event_loop().time()` with
  `time.time()` so `ActiveJob.started_at` matches the wall-clock semantics used
  by the synchronous worker and avoids `DeprecationWarning` on Python 3.12+.
- **Realtime events**: `RealtimeEvent.from_server_event` now stamps `timestamp`
  with timezone-aware UTC (`datetime.now(timezone.utc)`) instead of a naive
  local datetime, fixing `TypeError` when comparing client-side fallback
  timestamps against server-provided aware datetimes.
- Added the changelog file referenced by package metadata.
- Added missing `types-protobuf` dev dependency so `mypy --strict` passes in
  fresh environments.
- Updated GitHub Actions workflows to current checkout, Python setup, and
  artifact actions.

## Previous releases

Earlier release history is available in the repository tags.
