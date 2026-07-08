# Changelog

All notable changes to the Spooled Python SDK are documented here.

## [1.0.16] - 2026-07-08

### Fixed

- `spooled.__version__` now resolves from the installed package metadata instead
  of a hardcoded literal that lagged the real release (was stuck at `1.0.1`).

## [1.0.15] - 2026-07-08

### Fixed

- **Requests could hang forever**: a per-request `timeout=None` disabled the client
  timeout; the client-level timeout now always applies (sync + async).
- **Opaque job payloads were mangled**: request key-case conversion recursed into
  user `payload`/`result`/`metadata`; those subtrees are now preserved verbatim.
- **Realtime WebSocket auth** exchanges the API key for a JWT and connects with
  `?token=`; standalone SSE clients honor `auto_reconnect`; SSE `disconnect()` no
  longer wipes queue/job filters; the unified client no longer double-consumes the
  socket.
- Auto token-refresh on 401 is now wired (was dead code).
- `Retry-After` is honored on 429; query params are URL-encoded; non-idempotent
  POSTs are not retried unless an idempotency key is present.
- Unknown server event types are dropped instead of misrouted as errors; the
  server-provided event timestamp is preserved.

## [1.0.14] - 2026-07-07

### Security

- Raised the `protobuf` security floor to 5.29.6.

### Changed

- Commit `uv.lock` so installs are reproducible.

### Documentation

- Corrected the API key prefix and the realtime example in the README.

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
