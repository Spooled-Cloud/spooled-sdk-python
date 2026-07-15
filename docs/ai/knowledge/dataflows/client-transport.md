# Transport

- Defaults in `src/spooled/config.py`.
- gRPC enqueue method defaults `max_retries=3`, `timeout_seconds=300` (`grpc/client.py`) — always sends values (not omit).
- Ingest: custom only (no GitHub/Stripe helpers).
