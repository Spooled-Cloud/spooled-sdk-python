# Findings (Python SDK)

| ID | Sev | Summary | Evidence |
|----|-----|---------|----------|
| PS-01 | P3 | gRPC always sends 3/300 (cannot omit to server settings) | `src/spooled/grpc/client.py` ~633–634 |
| PS-02 | P3 | Worker progress no-op | `src/spooled/worker/types.py` ~42–45 |
| PS-03 | P3 | No GitHub/Stripe ingest helpers | ingest module |
