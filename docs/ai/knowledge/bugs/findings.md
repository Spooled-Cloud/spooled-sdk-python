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
