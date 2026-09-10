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
