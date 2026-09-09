# Parity notes (Python)

- Async client unique among SDKs.
- REST/gRPC job create omits unset retry/timeout defaults; explicit values are still sent.
- Worker progress emits local job logs only; Go remains the SDK with backend-persisted `POST /jobs/{id}/progress`.
- Webhook update bodies come from `UpdateOutgoingWebhookParams.to_payload()`, not a bare `model_dump(exclude_none=True)`: unmentioned fields stay omitted, and a `secret` the caller explicitly set to `None` is sent as JSON `null` so the server clears it.
- Worker registration forwards an optional `worker_id` (upsert on restart); sync worker, async worker, and `SpooledWorkerOptions` all expose it and drop it when unset.
- Workflow job list/get/status are not their own REST routes. `GET /workflows/{id}` carries jobs + dependencies; `workflows.jobs.list` reads that document. `POST /jobs/{id}/dependencies` takes `depends_on` + `dependency_mode` and returns `dependencies_added` / `dependencies_met`.
- `GET /workflows/{id}` is `WorkflowDetailResponse`: job counts are under `progress` (`total`/`completed`/`failed`), not top-level `total_jobs` like list/cancel/retry. `WorkflowResponse` maps those onto `total_jobs`/`completed_jobs`/`failed_jobs`/`progress_percent`.
- `GET /jobs/{id}/dependencies` is `{ job_id, dependencies, dependents, dependencies_met }` with `{ job_id, queue_name, status }` edges. `completed` is derived from `status == "completed"`.
- Email availability is `GET /auth/check-email?email=`, not `/auth/email/check`. The body is `available`, `exists`, `signup_enabled`.
- Email login start is `POST /auth/email/start` → `{ message, email_sent_to }`, not `{ email_to }` / `{ success, message }`.
- Slug check is `GET /organizations/check-slug?slug=` → `{ available, valid, error, suggestion }`, not `{ slug }`.
- Admin hard delete is `DELETE /admin/organizations/{id}?hard_delete=true`, not `?hard=true`.
- `GET /admin/organizations` is `{ organizations, total, limit, offset }`, not a bare array. List rows omit `settings`.
- Job list/DLQ summaries send `attempt` and `max_retries`, not `retry_count`. `JobSummary.retry_count` maps from `attempt`.
- `GET /jobs` summaries include `job_type` from `payload.job_type` (empty string when absent). `JobSummary.job_type` maps that field.
- List/DLQ summaries include `last_error` (null when none). `JobSummary.last_error` maps that field.
- `GET /jobs/status` returns `{ id, status, queue_name, retry_count, created_at, completed_at }` (no `attempt`/`max_retries`).
