# Changelog

All notable changes to the Spooled Python SDK are documented here.

## [1.0.22] - 2026-07-12

### Fixed

- The default REST `User-Agent` now derives from the canonical package version
  instead of remaining stuck at `spooled-python/1.0.1`.
- Direct `SpooledWorkerOptions` construction now defaults its registration
  version to the canonical package version instead of `1.0.0`.
- Added release-contract coverage for project metadata, source fallback, REST
  user-agent, worker options, sync/async workers, and gRPC registration.

### Changed

- Added a release advisory checklist and strengthened the GitHub Release workflow
  to validate release metadata and run the normal lint, type, test, build, and
  artifact checks before Trusted Publishing uploads to PyPI.

## [1.0.21] - 2026-07-12

### Fixed

- Aligned the optional gRPC runtime and generator floors with the checked-in
  generated stubs (`grpcio`/`grpcio-tools` 1.80.0+, protobuf 6.33.5+) and
  regenerated the stubs and lockfile.
- Worker and gRPC registration defaults now use the package's canonical version
  instead of reporting `1.0.0`; source-only imports retain a synchronized
  `1.0.21` fallback when installed package metadata is unavailable.
- Sync and async workers now bind heartbeat, settlement, and cleanup to the exact
  active execution, so a stale lease cannot borrow, settle, remove, or cancel a
  replacement execution for the same job ID.
- Added regression coverage for bidirectional stream lease fencing, async
  heartbeat lease serialization, unary complete/fail/renew wire fields, and
  generated-stub imports at the declared minimum dependency versions.

## [1.0.20] - 2026-07-11

### Added

- **Lease fencing (backend v0.1.94, audit F9).** The claim/dequeue response now
  carries a `lease_id` fencing token; the SDK captures it on `ClaimedJob` and
  the workers echo it back on complete/fail/heartbeat. A stale token is
  rejected server-side with `409 LEASE_EXPIRED` (gRPC `FAILED_PRECONDITION`),
  so a worker whose lease was reclaimed can no longer complete or fail a job
  it no longer owns. Omitting the token preserves legacy behavior against
  older servers.
- **gRPC client fencing support.** `complete()`, `fail()`, and `renew_lease()`
  accept an optional `lease_id` keyword; `GrpcJob` exposes the `lease_id`
  returned on dequeue, and the `ProcessJobs` streaming request models carry it
  as well. Stubs regenerated from the v0.1.94 proto (`Job.lease_id = 19`,
  `CompleteRequest.lease_id = 4`, `FailRequest.lease_id = 5`,
  `RenewLeaseRequest.lease_id = 4`).

## [1.0.19] - 2026-07-09

### Fixed

- **Realtime WebSocket commands now use the backend `{"cmd": ...}` shape.**
  `subscribe`, `unsubscribe`, and `ping` previously serialized as
  `{"type": "subscribe"}`. The backend's `ClientCommand` enum is internally
  tagged with `cmd`, so those frames failed to deserialize server-side and the
  command was silently dropped. They now send
  `{"cmd": "subscribe", "queue": ..., "job_id": ...}` (and likewise for
  `unsubscribe`/`ping`), matching production.
- **`subscribe()`/`unsubscribe()` no longer block on an ack the server never
  sends.** The synchronous `WebSocketClient` waited up to `command_timeout`
  seconds for a subscribe/unsubscribe/ping acknowledgement and then raised
  `TimeoutError` — the backend sends no such response frame. Commands now fire
  and return immediately. Subscriptions are still tracked so they are re-sent on
  reconnect.
- **Server-Sent Events deliver the payload fields verbatim.** Each event is
  serialized adjacently-tagged as `{"type": "<PascalCase>", "data": {...}}` in
  the SSE `data:` field; the SDK now unwraps that envelope so typed handlers
  receive the inner fields (`job_id`, `result`, ...) instead of the wrapper.

Incoming events are still mapped from the backend's PascalCase `type`
(`JobCompleted`, `QueueStats`, ...) to the SDK's dotted event names
(`job.completed`, `queue.stats`, ...) before dispatch, and the untyped
catch-all handler continues to receive every event.

## [1.0.18] - 2026-07-09

### Fixed

- **Credentials are trimmed of surrounding whitespace.** API keys, access tokens,
  and refresh tokens read from a file or environment variable often carry a
  trailing newline; the client now trims them at config resolution (an
  all-whitespace value is treated as unset). Prevents a cryptic failure such as
  Go's `net/http: invalid header field value` on a newline-tainted key.

## [1.0.17] - 2026-07-08

### Fixed

- Realtime no longer exchanges the API key for a JWT via `POST /auth/login` on
  every (re)connect. The exchanged token is now cached on the client (sync and
  async) and reused across reconnects until it nears expiry, so reconnect storms
  no longer trip the login rate limiter and realtime can recover. The `exp`
  claim is read from the token (base64url-decoded, signature not verified) and
  refreshed ~60s early; a statically configured `access_token` is still used
  verbatim. The synchronous realtime client mints tokens through this cache on
  each (re)connect via a token provider, and `get_jwt_token(force_refresh=True)`
  forces a re-login when the server rejects the current token.

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
