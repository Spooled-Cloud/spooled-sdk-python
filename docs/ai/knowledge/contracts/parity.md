# Parity notes (Python)

- Async client unique among SDKs.
- REST/gRPC job create omits unset retry/timeout defaults; explicit values are still sent.
- Worker progress emits local job logs only; Go remains the SDK with backend-persisted `POST /jobs/{id}/progress`.
- Webhook update bodies come from `UpdateOutgoingWebhookParams.to_payload()`, not a bare `model_dump(exclude_none=True)`: unmentioned fields stay omitted, and a `secret` the caller explicitly set to `None` is sent as JSON `null` so the server clears it.
- Worker registration forwards an optional `worker_id` (upsert on restart); sync worker, async worker, and `SpooledWorkerOptions` all expose it and drop it when unset.
- Workflow job list/get/status are not their own REST routes. `GET /workflows/{id}` carries jobs + dependencies; `workflows.jobs.list` reads that document. `POST /jobs/{id}/dependencies` takes `depends_on` + `dependency_mode` and returns `dependencies_added` / `dependencies_met`.
- Email availability is `GET /auth/check-email?email=`, not `/auth/email/check`. The body is `available`, `exists`, `signup_enabled`.
