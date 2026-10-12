# Findings (Python SDK)

| ID | Sev | Summary | Evidence |
|----|-----|---------|----------|
| PS-01 | P3 | ~~gRPC always sends 3/300 (cannot omit to server settings)~~ **FIXED working tree** | `src/spooled/grpc/client.py`; `src/spooled/resources/jobs.py` |
| PS-02 | P3 | ~~Worker progress no-op~~ **FIXED working tree** — local job log | `src/spooled/worker/types.py` ~42–45 |
| PS-03 | P3 | No GitHub/Stripe ingest helpers | ingest module |
| PS-04 | P2 | ~~gRPC streams inherit unary 30s deadline~~ **FIXED working tree** | `src/spooled/grpc/client.py` |
| PS-05 | P3 | ~~Maintainer scripts fail Ruff unused-code checks~~ **FIXED working tree** | `scripts/test_local.py`; `scripts/verify_production.py` |
| PS-06 | P1 | ~~`check_email` called GET `/auth/email/check` (404)~~ **FIXED** | `src/spooled/resources/auth.py`; backend is `GET /auth/check-email` |
| PS-07 | P2 | ~~`start_email_login` read `email_to`; API sends `email_sent_to`~~ **FIXED** | `src/spooled/types/auth.py` |
| PS-08 | P2 | ~~`JobDependency.completed` always False (API never sends it)~~ **FIXED** | `src/spooled/types/workflows.py`; derived from `status == "completed"` |
| PS-09 | P2 | ~~`CheckSlugResponse` typed `slug`; dropped `error`/`suggestion`~~ **FIXED** | `src/spooled/types/organizations.py` |
| PS-10 | P1 | ~~`JobSummary.retry_count` always None; list JSON sends `attempt`~~ **FIXED** | `src/spooled/types/jobs.py` |
| PS-11 | P1 | ~~`BatchJobStatus` dropped `retry_count`/`created_at`/`completed_at`~~ **FIXED** | `src/spooled/types/jobs.py` |
| PS-12 | P1 | ~~`workflows.get()` left `total_jobs`/`completed_jobs`/`failed_jobs` None~~ **FIXED** | `src/spooled/types/workflows.py`; GET detail puts counts under `progress` |
| PS-13 | P2 | ~~`JobSummary` dropped `job_type` from `GET /jobs`~~ **FIXED** | `src/spooled/types/jobs.py`; summaries send `job_type` from payload |
| PS-14 | P2 | ~~`JobSummary` dropped `last_error` from list/DLQ~~ **FIXED** | `src/spooled/types/jobs.py`; summaries send `last_error` |
| PS-15 | P1 | ~~`admin.create_organization` validated `{organization, api_key}` as `Organization`~~ **FIXED** | `src/spooled/resources/admin.py`; returns `CreateOrganizationResponse` |
| PS-16 | P1 | ~~`auth.validate` dropped `claims` (org/queues/exp always empty)~~ **FIXED** | `src/spooled/types/auth.py`; POST `/auth/validate` is `{valid,error,claims}` |
| PS-17 | P1 | ~~`auth.logout` omitted refresh token so `/auth/refresh` survived~~ **FIXED** | `src/spooled/resources/auth.py`; POST `/auth/logout` body `refresh_token` |
| PS-18 | P1 | ~~`retry_delivery` POSTed `/deliveries/{id}/retry` and typed `{delivery_id,status}`~~ **FIXED** | `src/spooled/resources/webhooks.py`; route is `/retry/{delivery_id}` → `{success,message}` |
| PS-19 | P1 | ~~`ingest.custom` parsed empty 200 as `{job_id, created}` and raised on success~~ **FIXED** | `src/spooled/resources/ingest.py`; handler returns `StatusCode::OK` |
| PS-20 | P1 | ~~`ingest.custom` returned `None` and dropped `job_id` after backend started sending `WebhookResponse`~~ **FIXED** | `src/spooled/resources/ingest.py`; maps `job_id`/`queue_name`/`status` |
| PS-21 | P1 | ~~`Job.tags`/`Schedule.tags` as `dict[str, str]` rejected API JSON tags~~ **FIXED** | `src/spooled/types/jobs.py`, `src/spooled/types/schedules.py`; object-with-bool and string-array both valid |
| PS-22 | P1 | ~~`Job.payload`/`result` as `dict` rejected non-object JSON~~ **FIXED** | `src/spooled/types/jobs.py`; backend payload/result is `serde_json::Value` |
| PS-23 | P1 | ~~`Schedule.payload_template`/`metadata` as `dict` rejected non-object JSON~~ **FIXED** | `src/spooled/types/schedules.py`; backend is `serde_json::Value` |
| PS-24 | P1 | ~~`WorkflowJob.payload` as `dict` raised on string/array/bool JSON~~ **FIXED** | `src/spooled/types/workflows.py`; GET detail jobs send `serde_json::Value` |
| PS-25 | P1 | ~~Create/bulk/workflow-def/webhook-delivery `payload` still `dict` so non-object JSON raised~~ **FIXED** | `src/spooled/types/jobs.py`, `workflows.py`, `webhooks.py` |
| PS-26 | P1 | ~~`ingest.custom` `payload` as `dict` raised on string/array/bool JSON~~ **FIXED** | `src/spooled/resources/ingest.py`; backend `CustomWebhookRequest.payload` is `serde_json::Value` |
| PS-27 | P1 | ~~DLQ purge sent `older_than_days`/`job_ids` and omitted required `confirm`~~ **FIXED** | `src/spooled/types/jobs.py`; backend is `{queue_name?, older_than?, limit?, confirm}` |
| PS-28 | P1 | ~~`queues.delete` never sent `delete_jobs`, so a busy queue always 409'd~~ **FIXED** | `src/spooled/resources/queues.py`; backend `DELETE /queues/{name}?delete_jobs=true` |
| PS-29 | P1 | ~~`WorkflowJob` dropped `result`/`error`/`metadata` from GET /workflows/{id}~~ **FIXED** | `src/spooled/types/workflows.py`; backend `WorkflowJobResponse` |
| PS-30 | P2  | ~~`CreateWorkflowResponse` dropped `status` from POST /workflows~~ **FIXED** | `src/spooled/types/workflows.py`; backend always sends `status` |
| PS-31 | P1  | ~~`WorkflowResponse.metadata` as `dict` raised on string/array JSON~~ **FIXED** | `src/spooled/types/workflows.py`; backend metadata is `serde_json::Value` |
| PS-32 | P1  | ~~`Worker.metadata` as `dict` raised on string/array JSON~~ **FIXED** | `src/spooled/types/workers.py`; backend `WorkerResponse.metadata` is `serde_json::Value` |
| PS-33 | P1  | ~~`QueueConfig.settings` as `dict` raised on string/array JSON~~ **FIXED** | `src/spooled/types/queues.py`; backend `QueueConfig.settings` is `serde_json::Value` |
| PS-34 | P1  | ~~`Organization.settings`/`custom_limits` as `dict` raised on string/array JSON~~ **FIXED** | `src/spooled/types/organizations.py`; backend is `serde_json::Value` |
| PS-35 | P1  | ~~`SpooledWorkerOptions.metadata` as `dict` raised on string/array JSON~~ **FIXED** | `src/spooled/worker/types.py`; backend register metadata is `serde_json::Value` |
| PS-36 | P1  | ~~`create_error_from_response` AttributeError on non-object JSON error bodies~~ **FIXED** | `src/spooled/errors.py`; `response.json()` can be a string/array/number |
| PS-37 | P1  | ~~Realtime parse ValidationError/AttributeError on non-object JSON dropped the WS/SSE loop~~ **FIXED** | `src/spooled/realtime/events.py`; `websocket.py`; `unified.py` |
| PS-38 | P2  | ~~`auth.me()` dropped nested `organization` from GET /auth/me~~ **FIXED** | `src/spooled/types/auth.py`; backend `CurrentUserResponse.organization` |
| PS-39 | P2  | ~~`schedules.create` always sent `max_retries=3`/`timeout_seconds=300`~~ **FIXED** | `src/spooled/resources/schedules.py`; backend omit uses `QUEUE_DEFAULT_*` |
| PS-40 | P2  | ~~`CreateJobParams` `extra=forbid` rejected `completion_webhook_secret`~~ **FIXED** | `src/spooled/types/jobs.py`; backend `CreateJobRequest` since 0.1.109 |
| PS-41 | P1 | ~~Graceful `stop()` aborted handlers first and dropped their results; deregister re-queued the job (duplicate run)~~ **FIXED 1.3.0** | `worker/worker.py, worker/async_worker.py`; Drain: no abort until shutdown_timeout, ack always, deregister last (SDKNP-01) |
| PS-42 | P1 | ~~`get_jwt_token()`/`realtime()` replaced the REST bearer with a 24 h JWT~~ **FIXED 1.3.0** | `client.py, async_client.py`; JWT kept in realtime layer only (SDKNP-02) |
| PS-43 | P2 | ~~SSE clients used httpx 5 s read timeout~~ **FIXED 1.3.0** | `realtime/sse.py, unified.py`; SSE_TIMEOUT read 60 s (SDKNP-03) |
| PS-44 | P2 | ~~SSE ignored HTTP status, reset retry counter on connect; unified SSE went dead on clean end~~ **FIXED 1.3.0** | `realtime/sse.py, unified.py`; Typed errors, counter reset on event, reconnect on clean end (SDKNP-04) |
| PS-45 | P2 | ~~complete/fail/heartbeat acks never retried~~ **FIXED 1.3.0** | `resources/jobs.py, workers.py, utils/http.py`; idempotent=True (SDKNP-05) |
| PS-46 | P2 | ~~429 QUOTA_EXCEEDED retried with long sleeps and tripped the breaker~~ **FIXED 1.3.0** | `errors.py, utils/retry.py`; QuotaExceededError, not retryable (SDKNP-06) |
| PS-47 | P2 | ~~Concurrent 401s: only one request refreshed~~ **FIXED 1.3.0** | `utils/http.py, utils/async_http.py`; Single-flight refresh (SDKNP-07) |
| PS-48 | P2 | ~~`queues.pause(name)` without reason sent empty JSON body (400)~~ **FIXED 1.3.0** | `resources/queues.py`; Send `{}` (SDKNP-08) |
| PS-49 | P2 | ~~`client.grpc` ignored `grpc_address`~~ **FIXED 1.3.0** | `client.py, async_client.py`; Use grpc_address (SDKNP-11) |
| PS-50 | P2 | ~~`with_options()` dropped most configuration~~ **FIXED 1.3.0** | `config.py, client.py`; merge_client_config (SDKNP-12) |
| PS-51 | P2 | ~~`dlq.purge({})` confirmed itself~~ **FIXED 1.3.0** | `types/jobs.py`; confirm required (SDKNP-13) |
| PS-52 | P2 | ~~422 not mapped to ValidationError~~ **FIXED 1.3.0** | `errors.py`; Mapped (SDKNP-14) |
| PS-53 | P2 | ~~`timeout_seconds` never enforced by SDK workers~~ **FIXED 1.3.0** | `worker/*.py`; Timer / wait with fail "Job timeout exceeded" (SDKNP-16) |
| PS-54 | P2 | ~~gRPC `lease_id` optional in types, required by server~~ **FIXED 1.3.0** | `grpc/client.py`; Required (SDKNP-17) |
| PS-55 | P2 | ~~Workflow jobs returned invented `key: ""`~~ **FIXED 1.3.0** | `types/workflows.py, resources/workflows.py`; key is None (SDKNP-18) |
| PS-56 | P3 | ~~`clear_webhook_token` can never succeed~~ **FIXED 1.3.0** | `resources/organizations.py`; UnsupportedOperationError (SDKNP-26) |
| PS-57 | P2 | ~~Empty/over-long fail text rejected with 400, job stuck until lease expiry~~ **FIXED 1.3.0** | `types/jobs.py, worker/*.py`; coerce_fail_error (brief item 4) |
| PS-59 | P2 | ~~gRPC `fail(retry=False)` and ProcessJobs fail retried instead of dead-lettering (stale proto, plain `bool retry`)~~ **FIXED 1.4.0** | `proto/spooled.proto, grpc/client.py`; Proto synced with backend (`optional bool retry`, `optional string worker_id`), stubs regenerated, field set only when not None (1.4.0) |
