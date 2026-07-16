# Findings (Python SDK)

| ID | Sev | Summary | Evidence |
|----|-----|---------|----------|
| PS-01 | P3 | ~~gRPC always sends 3/300 (cannot omit to server settings)~~ **FIXED working tree** | `src/spooled/grpc/client.py`; `src/spooled/resources/jobs.py` |
| PS-02 | P3 | ~~Worker progress no-op~~ **FIXED working tree** — local job log | `src/spooled/worker/types.py` ~42–45 |
| PS-03 | P3 | No GitHub/Stripe ingest helpers | ingest module |
| PS-04 | P2 | ~~gRPC streams inherit unary 30s deadline~~ **FIXED working tree** | `src/spooled/grpc/client.py` |
| PS-05 | P3 | ~~Maintainer scripts fail Ruff unused-code checks~~ **FIXED working tree** | `scripts/test_local.py`; `scripts/verify_production.py` |
