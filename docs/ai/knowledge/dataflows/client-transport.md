# Transport

- Defaults in `src/spooled/config.py`.
- REST and gRPC create/enqueue omit unset retry/timeout values so backend queue/server defaults apply; explicit values are still sent.
- gRPC unary calls use the configured per-call timeout; long-lived streams default to no deadline unless `stream_timeout` is set.
- Ingest: custom only (no GitHub/Stripe helpers).
