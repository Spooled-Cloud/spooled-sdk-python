# Parity notes (Python)

- Async client unique among SDKs.
- REST/gRPC job create omits unset retry/timeout defaults; explicit values are still sent.
- Worker progress emits local job logs only; Go remains the SDK with backend-persisted `POST /jobs/{id}/progress`.
