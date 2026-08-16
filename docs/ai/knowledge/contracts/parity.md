# Parity notes (Python)

- Async client unique among SDKs.
- REST/gRPC job create omits unset retry/timeout defaults; explicit values are still sent.
- Worker progress emits local job logs only; Go remains the SDK with backend-persisted `POST /jobs/{id}/progress`.
- Webhook update bodies come from `UpdateOutgoingWebhookParams.to_payload()`, not a bare `model_dump(exclude_none=True)`: unmentioned fields stay omitted, and a `secret` the caller explicitly set to `None` is sent as JSON `null` so the server clears it.
- Worker registration forwards an optional `worker_id` (upsert on restart); sync worker, async worker, and `SpooledWorkerOptions` all expose it and drop it when unset.
