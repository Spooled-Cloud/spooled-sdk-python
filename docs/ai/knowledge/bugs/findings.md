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
