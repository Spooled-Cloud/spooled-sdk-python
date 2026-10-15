# Changelog

All notable changes to the Spooled Python SDK are documented here.

## [1.5.0] - 2026-10-15

Workers stop working a job whose lease is gone, and a partial DLQ retry now
reports the jobs it left behind. Everything is additive: existing calls,
parameters and return values keep working, and the fixes only change behaviour
that was wrong.

### Fixed

- **A worker no longer completes or fails a job after losing its lease.** A job
  heartbeat answered with HTTP 409 `LEASE_EXPIRED` (the lease timed out, or
  `lease_id` no longer matches the job's current lease) was logged and retried on
  the next tick. The handler kept running and then sent `complete` or `fail` with
  the stale lease, so the same payload could run on two workers. The sync and
  async workers now treat that 409, on a heartbeat, `complete` or `fail`, as a
  lost lease: heartbeats and the job timeout timer stop, `ctx.signal` is set, the
  handler's result is dropped and no further ack is sent for that job. The async
  worker also cancels the handler task. A sync handler runs in a thread that
  cannot be killed, so it should watch `ctx.signal` to stop early. Other 409
  answers, such as "Job is already completed" on a replayed ack, behave as before.
- **`RetryDlqResponse.job_ids` and `retried_jobs` are the same ids.** The API
  answers with `retried_jobs`, so `job_ids` was `None`. It now mirrors
  `retried_jobs`, and a response that only carries the older `job_ids` fills
  `retried_jobs`.

### Added

- `RetryDlqResponse.skipped_jobs`: the ids a DLQ retry left dead-lettered because
  reviving their workflow would pass the plan's `max_workflows`. A partial retry
  is still HTTP 200, so `retried_count` and `skipped_jobs` are the only sign that
  some jobs were not retried.
- Worker event `job:lease_lost`, with `JobLeaseLostEventData` (`job_id`,
  `queue_name`, `lease_id`, `operation` as `"heartbeat"`, `"complete"` or
  `"fail"`, and the `error`), exported from `spooled.worker`.
- `spooled.errors.is_lease_expired(error)`: true for a `ConflictError` with code
  `LEASE_EXPIRED`. The API uses that one code both when the lease timed out and
  when `lease_id` does not match the job's current lease.

## [1.4.0] - 2026-10-12

Catches up with backend 0.1.122. Everything is additive: existing calls,
parameters and return values keep working, and the two fixes only change
behaviour that was wrong.

### Fixed

- **`webhooks.list()`, `get()` and `update()` no longer fail on newer webhooks.**
  A webhook subscribed to `job.deadlettered`, `job.retried`, `workflow.completed`
  or `workflow.failed` (which the dashboard already offers) made every read raise
  `pydantic.ValidationError`, for the whole organization's list. `update()` raised
  after the server had applied the change. Webhook `events`, `format` and
  `last_status` now accept values this SDK does not know yet.
- **gRPC `queue.fail(..., retry=False)` dead-letters the job again.** The bundled
  proto had a plain `bool retry`, so `False` was never put on the wire and the
  server retried the job up to `max_retries`. The proto is synced with the backend
  (`optional bool retry = 4`) and the stubs regenerated; the ProcessJobs `fail`
  message is fixed the same way. `retry=None` leaves the field unset (server
  default: retry).
- No response model fails on a new enum value any more: job, worker and workflow
  `status`, plan tiers (`plan_tier`, `UsageInfo.plan`), webhook delivery `status`
  and `dependency_mode` keep an unknown value as a string.
- gRPC `ALREADY_EXISTS` maps to `ConflictError` (was `ServerError`).
- `scripts/generate_grpc.sh` writes LF line endings on Windows too.

### Added

- Webhook `format` (`json`, `slack`, `discord`, `teams`) on create, update and
  read, and the four new events on `WebhookEvent`.
- `client.jobs.list()` filters: `status` as a list or `"failed,deadletter"`,
  `q`, `job_type`, `created_after`, `created_before` (RFC 3339; a naive datetime
  is UTC). `jobs.dlq.list()` takes the same filters except `status`. `tag`
  accepts up to 1024 characters (was 64; the API allows 1024 bytes).
- `jobs.list()`, `jobs.dlq.list()` and the new `jobs.history()` return a `Page`:
  still a `list`, plus `has_more` from the `X-Has-More` header.
- `client.jobs.history(job_id, {"order_dir": "desc", "limit": 50})` for
  `GET /jobs/{id}/history` (`JobHistoryEvent`: `id`, `job_id`, `event_type`,
  `worker_id`, `details`, `created_at`).
- `Worker.jobs_processed` / `jobs_failed` and the same on `WorkerSummary`.
- `client.webhooks.list_inbound_deliveries()` for the inbound webhook log
  (`GET /webhooks/deliveries`, filters `status`, `since`, `queue_name`).
- `client.rate_limit`: the `X-RateLimit-Limit`, `-Remaining`, `-Reset` (Unix
  seconds, as an aware UTC datetime) and `-Scope` values of the latest response,
  which the API sends on every response. `RateLimitError.scope` is new.
- gRPC `workers.register(..., worker_id=...)` (stable id upsert) and
  `GrpcRegisterWorkerRequest.worker_id`.
- `client.metrics.get(token=...)`: `GET /metrics` takes the server's metrics
  token, not an API key.

### Docs

- The README no longer says the API sends no `X-RateLimit-*` headers, and no
  longer claims `SpooledClient` reads `SPOOLED_API_KEY` / `SPOOLED_BASE_URL` (it
  does not; the examples use those names). `lease_id` is documented as required
  on REST `complete`/`fail`/`heartbeat` (422 without it) and gRPC settlement, and
  the gRPC `Struct` limits are spelled out: only object payloads, and integers of
  2^53 and above lose precision over gRPC (REST keeps them).
- `scripts/test_local.py` / `test_production.py` follow the current API: they
  send `lease_id`, `confirm=True` on DLQ purge, accept `sp_` keys, expect `/metrics`
  to answer 401 without the metrics token, cover the additions above, and skip
  steps with side effects outside the test organization (new organization, login
  email, billing portal) against a non-local server unless `ALLOW_UNSAFE=1`.

## [1.3.0] - 2026-10-10

Worker shutdown and failure semantics, realtime auth and several client defaults
change, so this is a minor release. Everything below was found by the 2026-10-10
SDK audit and is covered by new unit tests; sync and async clients/workers get
every fix.

### Changed (read before upgrading)

- **`stop()` now drains instead of aborting.** It stops claiming jobs, lets
  running handlers finish for up to `shutdown_timeout` seconds, and still sends
  `complete` (or `fail`) for a handler that returned (or raised) in that window.
  `ctx.signal` is no longer set when `stop()` starts; it is set only when a
  handler outlives the timeout (it is then failed with "Worker shutdown timeout",
  and the async handler is cancelled) or exceeds the job's `timeout_seconds`.
  Job heartbeats keep running during the drain and the worker deregisters last.
  `start()` now returns only after `stop()` has finished. Handlers that polled
  `ctx.signal` to react to shutdown should rely on `shutdown_timeout` instead.
- **`PurgeDlqParams.confirm` has no default.** `client.jobs.dlq.purge({})` used to
  confirm on your behalf and delete every dead-lettered job of the organization;
  it now raises a validation error. Pass `"confirm": True` explicitly.
- **gRPC `complete`, `fail` and `renew_lease` require `lease_id`** (keyword-only,
  also on `GrpcCompleteRequest` / `GrpcFailRequest` / `GrpcRenewLeaseRequest`).
  The server already rejected settlement without one with `INVALID_ARGUMENT`.
- **`client.grpc` dials `grpc_address`** (default `grpc.spooled.cloud:443`, TLS
  unless the host is local). It used to dial `<api host>:50051` and ignore the
  setting, which cannot reach Spooled Cloud. Self-hosted users set `grpc_address`.
- **`WorkflowJob.key` and `WorkflowJobStatus.key` are `None`** instead of `""`:
  `GET /workflows/{id}` does not return job keys. Map `job_id` to a key with the
  `job_ids` from `workflows.create()`.
- **`organizations.clear_webhook_token()` is deprecated** and raises the new
  `UnsupportedOperationError` without a network call: the API always rejects it.
  Rotate the token with `regenerate_webhook_token()`.
- `SpooledClient(admin_key=...)` alone is now accepted (admin endpoints only).

### Fixed

- **A handler that finished during shutdown was dropped, then re-run.** See above;
  the job used to be re-queued by deregistering and executed twice.
- **`timeout_seconds` is enforced.** A handler running past its job's timeout is
  signalled (`ctx.signal`), the job is failed with "Job timeout exceeded" and its
  lease is no longer extended. A sync handler thread cannot be killed, so it keeps
  occupying a concurrency slot until it returns; the async handler is cancelled.
- **Failure text is always accepted.** An empty error becomes "Job failed" and
  anything over 2048 characters is cut to 2048 before `POST /jobs/{id}/fail`
  (the API answered 400, leaving the job `processing` until its lease expired).
- **Acks are retried.** `jobs.complete`, `jobs.fail`, `jobs.heartbeat` and
  `workers.heartbeat` retry network errors, timeouts, 5xx and 408 (they are
  lease-fenced, so a replay is safe). A failed ack is reported through the
  worker's `error` event instead of only the debug log.
- **A plan limit is not retried.** A 429 with code `QUOTA_EXCEEDED` (no
  `Retry-After`) raises the new `QuotaExceededError` (a `RateLimitError`) at once
  instead of sleeping 3 x 30 s, and no longer counts toward the circuit breaker,
  so a full quota cannot block worker acks and reads.
- **`get_jwt_token()` / `realtime()` no longer replace the REST bearer.** For an
  API-key client the 24 h JWT became the bearer of every later REST call and was
  never renewed, so everything returned 401 a day later. The realtime transport
  keeps its own cached token (renewed before it expires; the async `realtime()`
  now supplies a token provider too), and a configured `access_token` with a
  `refresh_token` is renewed before it expires.
- **Concurrent 401s share one token refresh.** Only one of N simultaneous
  requests used to recover; the rest raised `AuthenticationError`.
- **SSE clients no longer use httpx's 5 s read timeout** (60 s now, the server
  sends keep-alives every 15 s), which reconnected quiet streams every 5 s and
  lost the events in the gap.
- **SSE checks the HTTP status.** A 401/403/404 raises the typed error and stops
  instead of reconnecting once a second forever; 429/5xx back off and are
  retried. The retry counter is restored by a delivered event, not by a mere
  connect, so a failing stream runs out of attempts. A job stream (`job_id`) ends
  after the job's terminal status instead of replaying it on every reconnect, and
  the unified `realtime(type="sse")` client reconnects when the server ends the
  stream (its 30 minute cap) and stops, with `last_error` and an `error` event,
  on a rejected token.
- **`queues.pause(name)` without a reason works** (it sent an empty body with a
  JSON content type, which the API answers with 400).
- **`with_options()` keeps the whole configuration** (headers, retry, circuit
  breaker, user agent, timeouts, `grpc_address`, `ws_url`) instead of resetting
  everything but credentials, base URL, timeout and debug.
- **422 responses raise `ValidationError`** (like 400); `details` may be a list.
- Schedule name/queue name and workflow name/job queue name accept up to 255
  characters (the API limit), not 100.
- Async worker keeps references to its per-job tasks and tracks claimed jobs
  immediately, so a poll cannot over-claim.
- gRPC TLS auto-detection recognises `[::1]:port` as local.
- Removed a dead placeholder in `AsyncHttpClient.request()`.

## [1.2.2] - 2026-09-26

### Fixed

- **Synchronous SSE never delivered an event.** `SSEClient` and
  `realtime(type="sse")` had two stacked bugs, found by running them against the
  production API: they entered `httpx.Client.stream(...)` by hand and dropped its
  context manager, so the garbage collector closed the response straight away
  ("the stream has been closed"); and they passed `iter_lines()` to `sseclient`,
  which needs raw bytes to find event boundaries and raised `TypeError` on the
  first line. Both now use `send(..., stream=True)` and `iter_bytes()`, and
  `AsyncSSEClient` keeps its response open the same way. Verified live:
  `job.created` and `job.completed` arrive on all three clients.

## [1.2.1] - 2026-09-26

### Fixed

- **SSE queue subscriptions stream job events.** `SSEClient(queue=...)`,
  `AsyncSSEClient(queue=...)` and `realtime(type="sse").subscribe(SubscriptionFilter(queue=...))`
  connected to `/events/queues/{name}`, which only carries `queue.stats`, so
  `job.created` / `job.completed` handlers never fired. They now use
  `/events?queue={name}` (URL-encoded). Needs API 0.1.114+, where
  `/api/v1/events` started forwarding job events.

## [1.2.0] - 2026-09-10

A contract-parity pass against the backend: every fix below is a place where
this SDK's route, request shape, or response model disagreed with what the API
actually serves. Pair it with backend `0.1.112`, which supplies the response
fields several of these now read.

### Fixed

- `Schedule.payload_template` and `Schedule.metadata` now accept any JSON.
  They were typed `dict[str, Any]`, so `GET /schedules/{id}` raised
  `ValidationError` on a string, array, or boolean.
- `Job.payload` / `Job.result`, `ClaimedJob.payload`, and
  `CompleteJobParams.result` now accept any JSON. They were typed
  `dict[str, Any]`, so `GET /jobs/{id}` and claim/complete raised
  `ValidationError` on a string, array, or boolean (backend
  `serde_json::Value`).
- `Job.tags` and `Schedule.tags` now accept the API's JSON tags: an object
  (`{"urgent": true}`) or a string array (`["urgent"]`). They were typed
  `dict[str, str]`, so `GET /jobs/{id}` and `GET /schedules/{id}` raised
  `ValidationError` on either documented shape. Create/update params match.
- `ingest.custom` (sync and async) now maps OpenAPI `WebhookResponse`
  (`job_id`, `queue_name`, `status`). It previously required `{job_id, created}`
  (raised on empty 200) then returned `None` and dropped the job id the API
  actually sends. An empty 200 still maps to unset fields.
- `auth.logout` (sync and async) now sends the refresh token in the body.
  Without it the access token is blacklisted but `/auth/refresh` still mints a
  new pair, so logout did not end the session. The stored refresh token is used
  when the argument is omitted, matching the Node and PHP SDKs.
- `auth.validate` now maps `claims.org_id` / `api_key_id` / `queues` / `exp`
  onto `organization_id` / `api_key_id` / `queues` / `expires_at`. It previously
  looked for top-level `organization_id` and `expires_at`, which the API never
  sends, so a valid token looked empty.
- `auth.check_email` (sync and async) now calls `GET /auth/check-email`. It
  previously requested `GET /auth/email/check`, which is not a backend route, so
  every check 404'd. The response model now also reads `available` and
  `signup_enabled`, which the handler always sends.
- `auth.start_email_login` now reads `email_sent_to` from
  `POST /auth/email/start`. It previously looked for `email_to`, which the API
  never sends, so the masked address was always `None`.
- `workflows.jobs.get_dependencies` now derives `JobDependency.completed` from
  `status == "completed"`. The API never sends `completed`, so the flag was
  always `False`.
- `organizations.check_slug` now reads `error` and `suggestion` from
  `GET /organizations/check-slug`. It previously typed `slug`, which the API
  never sends, so a taken slug never offered an alternative.
- `JobSummary.retry_count` now maps `attempt` from `GET /jobs` and
  `GET /jobs/dlq`. Those list bodies send `attempt` and `max_retries`, not
  `retry_count`, so the count was always `None`.
- `BatchJobStatus` now reads `retry_count`, `created_at`, and `completed_at`
  from `GET /jobs/status`. It previously typed only `id`/`status`/`queue_name`,
  so retry count and timestamps were dropped.
- `admin.create_organization` (sync and async) now returns
  `CreateOrganizationResponse`. `POST /admin/organizations` sends
  `{organization, api_key}`; validating that wrapper as `Organization` raised
  on every create and dropped the one-time key.
- `queues.delete()` sends `delete_jobs`, and `jobs.dlq.purge()` sends `confirm`
  and `older_than`. Both parameters exist on the API; the SDK previously
  dropped them, so "delete the jobs too" silently deleted only the config.
- `ingest.custom()` maps OpenAPI `WebhookResponse` (`job_id`, `queue_name`,
  `status`). It previously required a `{job_id, created}` body that the endpoint
  never sent. An empty 200 — a backend older than `0.1.112` — still maps to a
  response with those fields unset rather than raising.
- Job list and DLQ summaries read the `job_type` and `last_error` that backend
  `0.1.112` adds to `JobSummary`.

## [1.1.0] - 2026-08-16

### Added

- Optional stable `worker_id` on worker registration. Supplying the same id
  across restarts makes registration an upsert, so a restarting worker reuses
  its row instead of leaving the old one against the plan worker cap until the
  stale-worker reaper clears it (~2 minutes). Omitting it keeps the previous
  behaviour of a server-minted UUID. An id owned by another organization
  returns 409.
- `auto_disabled` in the outgoing-webhook `last_status` domain. The backend now
  disables a webhook after 20 consecutive failed deliveries; re-enable it by
  setting `enabled: true`, which is charged against the plan webhook cap and can
  therefore return `429 QUOTA_EXCEEDED`.

### Changed

- Webhook updates can now express clearing the signing secret distinctly from
  leaving it alone. Backend 0.1.111 treats an explicit `null` as a destructive
  clear, so an untouched secret must be omitted rather than serialised.
- `failure_count` on outgoing webhooks is now counted once per delivery rather
  than once per retry attempt, so for the same failures it is roughly 5x smaller
  than before.
- Documented that `last_used` on API keys is coarse (written at most once per
  key per five minutes) and that webhook delivery history is retained by plan
  rather than kept indefinitely.

### Note

- Backend 0.1.111 no longer accepts API keys in the query string on REST
  endpoints. This SDK sends credentials as an `Authorization` header on REST;
  SSE and WebSocket connections continue to use the query string, which the
  backend still supports for those routes.

## [1.0.24] - 2026-07-19

### Fixed

- REST and gRPC job creation now omit unset retry/timeout defaults so the backend queue/server policy can apply; explicitly provided values are still sent.
- Long-lived gRPC `StreamJobs` / `ProcessJobs` calls no longer inherit the unary 30-second deadline by default. Use `stream_timeout` to opt into a stream deadline; stream deadline errors now preserve that timeout in the SDK `TimeoutError`.
- Worker `progress()` now emits local job logs instead of silently no-oping.
- Maintainer scripts now pass Ruff unused-code checks.

## [1.0.23] - 2026-07-13

### Fixed

- Add default gRPC per-call deadlines and map `grpc.RpcError` statuses into the SDK error hierarchy.

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
